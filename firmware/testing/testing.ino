  /*
 * ===================================================================
 *  SISTEM DETEKSI JATUH LANSIA + MONITOR VITALS
 *  Hardware : ESP32 + MPU6050 + MAX30102 + OLED SSD1306 (128x64)
 *
 *  Threshold dikalibrasi dari data rekaman nyata:
 *  - BERDIRI     : mag max 1.37G, std 0.037
 *  - JALAN       : mag max 1.74G, std 0.085
 *  - LARI        : mag max 2.79G, std 0.443
 *  - JATUH valid : mag max 2.27 - 8.00G
 * ===================================================================
 */

#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "MAX30105.h"
#include <WiFi.h>
#include <WiFiManager.h>
#include <PubSubClient.h>

// ===================================================================
// KONFIGURASI
// ===================================================================

// --- WiFi + MQTT ---
const char* mqtt_broker      = "broker.hivemq.com";
const int   mqtt_port        = 1883;
const char* mqtt_topic_data  = "eldersafe/vitals";
const char* mqtt_topic_fall  = "eldersafe/fall_alert";
const char* client_id        = "eldersafe_esp32_wristband";

#define MQTT_PUSH_INTERVAL_MS 1000

WiFiManager wifiManager;

// --- OLED ---
#define SCREEN_WIDTH   128
#define SCREEN_HEIGHT  64
#define OLED_ADDRESS   0x3C

// --- Fall Detection ---
#define IMPACT_THRESHOLD          2.8f
#define STRONG_MOVEMENT_THRESHOLD 1.0f
#define CONFIRM_DURATION_MS       2500
#define FALL_DISPLAY_LOCK_MS      30000

// --- Activity Detection (dari data kalibrasi) ---
#define ACTIVITY_WINDOW_SIZE  50    // 50 sample ~1 detik pada 50Hz
#define STD_THRESHOLD_JALAN   0.06f // di atas ini = jalan
#define STD_THRESHOLD_LARI    0.25f // di atas ini = lari

// --- Heart Rate / SpO2 ---
#define IR_FINGER_THRESHOLD  30000
#define DC_ALPHA             0.85f
#define PEAK_MIN_INTERVAL_MS 400
#define PEAK_MAX_INTERVAL_MS 1500
#define PEAK_THRESHOLD       300
#define WARMUP_MS            8000
#define LAST_DATA_HOLD_MS    2000

// --- History ---
#define HISTORY_SIZE 30

// --- Debug ---
#define DEBUG_MAGNITUDE         false
#define DEBUG_PRINT_INTERVAL_MS 200


// ===================================================================
// OBJEK SENSOR & DISPLAY
// ===================================================================

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
Adafruit_MPU6050 mpu;
MAX30105 particleSensor;

// --- Objek MQTT ---
WiFiClient mqttClient;
PubSubClient pubsubClient(mqttClient);

unsigned long lastMqttPush = 0;
bool mqttReady = false;


// ===================================================================
// STATE: FALL DETECTION
// ===================================================================

enum FallState { STATE_IDLE, STATE_IMPACT, STATE_CONFIRMING };

FallState fallState          = STATE_IDLE;
unsigned long fallStateStart = 0;
bool fallAlertActive         = false;
unsigned long fallAlertStart = 0;


// ===================================================================
// STATE: ACTIVITY DETECTION
// ===================================================================

enum ActivityLevel { ACTIVITY_DIAM, ACTIVITY_JALAN, ACTIVITY_LARI };

ActivityLevel currentActivity = ACTIVITY_DIAM;

// circular buffer buat rolling std
float magBuffer[ACTIVITY_WINDOW_SIZE];
int   magBufferIndex = 0;
bool  magBufferFull  = false;

const char* getActivityLabel() {
  switch (currentActivity) {
    case ACTIVITY_DIAM:  return "DIAM";
    case ACTIVITY_JALAN: return "JALAN";
    case ACTIVITY_LARI:  return "LARI";
    default:             return "DIAM";
  }
}


// ===================================================================
// STATE: VITALS
// ===================================================================

long irDC  = 0, redDC = 0;
bool dcInitialized = false;

long irFilteredPrev = 0;
long irPeakValue    = 0;
bool irRising       = false;

long lastPeakTime      = 0;
long peakIntervals[5]  = {0};
int  peakIntervalIndex = 0;
int  peakIntervalCount = 0;

int currentBPM    = -1;
int currentSpO2   = -1;
int lastValidBPM  = -1;
int lastValidSpO2 = -1;

long redMax = -100000, redMin = 100000;
long irMax  = -100000, irMin  = 100000;

bool fingerPresent               = false;
bool warmupDone                  = false;
unsigned long fingerDetectedTime = 0;
unsigned long fingerLiftedTime   = 0;


// ===================================================================
// STATE: HISTORY
// ===================================================================

int bpmHistory[HISTORY_SIZE];
int spo2History[HISTORY_SIZE];
int historyIndex      = 0;
int historyCount      = 0;
unsigned long lastHistorySave = 0;


// ===================================================================
// SETUP
// ===================================================================

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  Wire.begin();

  initDisplay();
  initMPU6050();
  initMAX30102();
  initHistoryBuffer();
  initWiFiAndMqtt();

  Serial.println("=== Sistem aktif ===");
}

void initDisplay() {
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("[ERROR] OLED tidak ditemukan!");
    while (1) delay(10);
  }
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("Inisialisasi...");
  display.display();
  Serial.println("[OK] OLED siap.");
}

void initMPU6050() {
  if (!mpu.begin()) {
    Serial.println("[ERROR] MPU6050 tidak ditemukan!");
    while (1) delay(10);
  }
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  Serial.println("[OK] MPU6050 siap.");
}

void initMAX30102() {
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("[ERROR] MAX30102 tidak ditemukan!");
    while (1) delay(10);
  }
  particleSensor.setup(90, 4, 2, 100, 411, 4096);
  particleSensor.setPulseAmplitudeRed(0x3F);
  particleSensor.setPulseAmplitudeIR(0x3F);
  Serial.println("[OK] MAX30102 siap.");
}

void initHistoryBuffer() {
  for (int i = 0; i < HISTORY_SIZE; i++) {
    bpmHistory[i]  = -1;
    spo2History[i] = -1;
  }
  for (int i = 0; i < ACTIVITY_WINDOW_SIZE; i++) {
    magBuffer[i] = 1.0f;
  }
}


// ===================================================================
// MODUL 5: FIREBASE DASHBOARD (WiFi + Realtime Database) — BARU
// ===================================================================

void initWiFiAndMqtt() {
  Serial.println("[WiFi] Memulai WiFiManager...");
  wifiManager.setConfigPortalTimeout(180);
  
  if (!wifiManager.autoConnect("ElderSafe-AP")) {
    Serial.println("[ERROR] Gagal konek WiFi. Restart perangkat.");
    delay(3000);
    ESP.restart();
    return;
  }

  Serial.println("[OK] WiFi tersambung.");
  Serial.print("[OK] SSID: "); Serial.println(WiFi.SSID());
  Serial.print("[OK] IP lokal: "); Serial.println(WiFi.localIP());

  pubsubClient.setServer(mqtt_broker, mqtt_port);
  pubsubClient.setCallback(mqttCallback);
  
  mqttReady = true;
  Serial.println("[OK] MQTT siap.");
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // callback untuk pesan dari broker (tidak dipakai saat ini)
}

void reconnectMqtt() {
  if (WiFi.status() != WL_CONNECTED) return;
  
  while (!pubsubClient.connected()) {
    Serial.print("[MQTT] Menyambung ke broker...");
    if (pubsubClient.connect(client_id)) {
      Serial.println("OK!");
    } else {
      Serial.println("Gagal. Retry dalam 5 detik.");
      delay(5000);
    }
  }
}

void pushMqttData(unsigned long now, bool isForce) {
  if (!mqttReady || WiFi.status() != WL_CONNECTED) return;
  if (!isForce && now - lastMqttPush < MQTT_PUSH_INTERVAL_MS) return;
  
  lastMqttPush = now;
  
  if (!pubsubClient.connected()) {
    reconnectMqtt();
  }
  
  int dispBPM  = getDisplayBPM(now);
  int dispSpO2 = getDisplaySpO2(now);
  int avgBPM   = getAverageFromHistory(bpmHistory);
  int avgSpO2  = getAverageFromHistory(spo2History);
  
  String json = buildStateJson(now);
  pubsubClient.publish(mqtt_topic_data, json.c_str());
}

// kumpulkan state terkini jadi satu JSON string, dipakai utk push ke Firebase
String buildStateJson(unsigned long now) {
  int dispBPM   = getDisplayBPM(now);
  int dispSpO2  = getDisplaySpO2(now);
  int avgBPM    = getAverageFromHistory(bpmHistory);
  int avgSpO2   = getAverageFromHistory(spo2History);

  unsigned long fallRemainingMs = 0;
  if (fallAlertActive) {
    long elapsed = (long)(now - fallAlertStart);
    long remain  = (long)FALL_DISPLAY_LOCK_MS - elapsed;
    fallRemainingMs = remain > 0 ? (unsigned long)remain : 0;
  }

  String fingerStatus;
  if (!fingerPresent) {
    bool inHold = lastValidBPM > 0 && now - fingerLiftedTime < LAST_DATA_HOLD_MS;
    fingerStatus = inHold ? "hold" : "no_finger";
  } else if (!warmupDone) {
    fingerStatus = "warming_up";
  } else {
    fingerStatus = "ok";
  }

  // dirakit manual (hindari dependency ArduinoJson tambahan, datanya simpel)
  String json = "{";
  json += "\"activity\":\"" + String(getActivityLabel()) + "\",";
  json += "\"fallAlert\":" + String(fallAlertActive ? "true" : "false") + ",";
  json += "\"fallRemainingMs\":" + String(fallRemainingMs) + ",";
  json += "\"fingerStatus\":\"" + fingerStatus + "\",";
  json += "\"bpm\":" + String(dispBPM) + ",";
  json += "\"spo2\":" + String(dispSpO2) + ",";
  json += "\"avgBpm30s\":" + String(avgBPM) + ",";
  json += "\"avgSpo230s\":" + String(avgSpO2) + ",";
  json += "\"uptimeMs\":" + String(now);
  json += "}";
  return json;
}

// ===================================================================
// MAIN LOOP
// ===================================================================

void loop() {
  unsigned long now = millis();

  if (pubsubClient.connected()) {
    pubsubClient.loop();
  }

  updateFallDetection(now);
  updateVitals(now);
  updateHistory(now);
  updateDisplay(now);
  pushMqttData(now, false);

  delay(10);
}


// ===================================================================
// MODUL 1: FALL DETECTION + ACTIVITY DETECTION (MPU6050)
// ===================================================================

float getAccelMagnitude() {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  float ax = a.acceleration.x / 9.81f;
  float ay = a.acceleration.y / 9.81f;
  float az = a.acceleration.z / 9.81f;

  return sqrt(ax*ax + ay*ay + az*az);
}

// hitung std dari buffer magnitude (rolling window)
float computeRollingStd() {
  int count = magBufferFull ? ACTIVITY_WINDOW_SIZE : magBufferIndex;
  if (count == 0) return 0;

  float sum = 0, sumSq = 0;
  for (int i = 0; i < count; i++) {
    sum   += magBuffer[i];
    sumSq += magBuffer[i] * magBuffer[i];
  }
  float avg = sum / count;
  float var = (sumSq / count) - (avg * avg);
  return sqrt(var > 0 ? var : 0);
}

void updateActivityLevel(float magnitude) {
  // masukkan magnitude ke circular buffer
  magBuffer[magBufferIndex] = magnitude;
  magBufferIndex = (magBufferIndex + 1) % ACTIVITY_WINDOW_SIZE;
  if (magBufferIndex == 0) magBufferFull = true;

  float std = computeRollingStd();

  if (std > STD_THRESHOLD_LARI) {
    currentActivity = ACTIVITY_LARI;
  } else if (std > STD_THRESHOLD_JALAN) {
    currentActivity = ACTIVITY_JALAN;
  } else {
    currentActivity = ACTIVITY_DIAM;
  }
}

void updateFallDetection(unsigned long now) {
  float magnitude = getAccelMagnitude();

  // update activity level dari magnitude yang sama
  updateActivityLevel(magnitude);

  if (DEBUG_MAGNITUDE) {
    static unsigned long lastPrint = 0;
    if (now - lastPrint >= DEBUG_PRINT_INTERVAL_MS) {
      lastPrint = now;
      Serial.print("Mag: "); Serial.print(magnitude);
      Serial.print(" | Aktivitas: "); Serial.println(getActivityLabel());
    }
  }

  switch (fallState) {
    case STATE_IDLE:       handleIdleState(magnitude, now);       break;
    case STATE_IMPACT:     handleImpactState(now);                break;
    case STATE_CONFIRMING: handleConfirmingState(magnitude, now); break;
  }
}

void handleIdleState(float magnitude, unsigned long now) {
  if (magnitude > IMPACT_THRESHOLD) {
    fallState      = STATE_IMPACT;
    fallStateStart = now;
    Serial.print("[WARNING] Impact! Mag="); Serial.println(magnitude);
  }
}

void handleImpactState(unsigned long now) {
  fallState      = STATE_CONFIRMING;
  fallStateStart = now;
  Serial.println("[INFO] Memantau pasca-impact...");
}

void handleConfirmingState(float magnitude, unsigned long now) {
  float deviation = abs(magnitude - 1.0f);

  if (deviation > STRONG_MOVEMENT_THRESHOLD) {
    Serial.println("[INFO] Gerakan kuat, kemungkinan bangun normal.");
    fallState = STATE_IDLE;
    return;
  }

  if (now - fallStateStart > CONFIRM_DURATION_MS) {
    Serial.println("=== !!! JATUH TERDETEKSI !!! ===");
    triggerFallAlert(now);
    fallState = STATE_IDLE;
  }
}

void triggerFallAlert(unsigned long now) {
  fallAlertActive = true;
  fallAlertStart  = now;

  // push segera, jangan nunggu siklus MQTT_PUSH_INTERVAL_MS —
  // ini kondisi kritis yang harus langsung sampai ke caretaker
  if (pubsubClient.connected()) {
    String fallAlert = "{\"alert\":\"JATUH TERDETEKSI\",\"timestamp\":" + String(now) + "}";
    pubsubClient.publish(mqtt_topic_fall, fallAlert.c_str());
  } else {
    pushMqttData(now, true);
  }
}


// ===================================================================
// MODUL 2: VITALS (MAX30102)
// ===================================================================

void updateVitals(unsigned long now) {
  if (!particleSensor.available()) {
    particleSensor.check();
    if (!particleSensor.available()) return;
  }

  long irValue  = particleSensor.getIR();
  long redValue = particleSensor.getRed();
  particleSensor.nextSample();

  if (irValue < IR_FINGER_THRESHOLD) {
    if (fingerPresent) {
      fingerPresent    = false;
      fingerLiftedTime = now;
    }
    return;
  }

  if (!fingerPresent) {
    fingerPresent      = true;
    warmupDone         = false;
    fingerDetectedTime = now;
    dcInitialized      = false;
    peakIntervalCount  = 0;
    peakIntervalIndex  = 0;
    lastPeakTime       = 0;
    currentBPM         = -1;
    currentSpO2        = -1;
    irFilteredPrev     = 0;
    irRising           = false;
  }

  if (!dcInitialized) {
    irDC  = irValue;
    redDC = redValue;
    dcInitialized = true;
  }

  irDC  = (DC_ALPHA * irDC)  + ((1 - DC_ALPHA) * irValue);
  redDC = (DC_ALPHA * redDC) + ((1 - DC_ALPHA) * redValue);

  long irFiltered  = irValue  - irDC;
  long redFiltered = redValue - redDC;

  if (!warmupDone) {
    if (now - fingerDetectedTime >= WARMUP_MS) {
      warmupDone = true;
    }
    return;
  }

  if (irFiltered > irFilteredPrev) {
    irRising    = true;
    irPeakValue = irFiltered;
  } else if (irRising && irFiltered < irFilteredPrev) {
    irRising = false;
    if (irPeakValue > PEAK_THRESHOLD) registerPeak(now);
    irPeakValue = 0;
  }
  irFilteredPrev = irFiltered;

  redMax = max(redMax, redFiltered); redMin = min(redMin, redFiltered);
  irMax  = max(irMax,  irFiltered);  irMin  = min(irMin,  irFiltered);

  static unsigned long lastSpo2Calc = 0;
  if (now - lastSpo2Calc >= 1000) {
    lastSpo2Calc = now;
    calculateSpO2();
  }
}

void registerPeak(unsigned long now) {
  long interval = now - lastPeakTime;

  if (lastPeakTime != 0 &&
      interval > PEAK_MIN_INTERVAL_MS &&
      interval < PEAK_MAX_INTERVAL_MS) {

    peakIntervals[peakIntervalIndex % 5] = interval;
    peakIntervalIndex++;
    if (peakIntervalCount < 5) peakIntervalCount++;

    long sum = 0;
    for (int i = 0; i < peakIntervalCount; i++) sum += peakIntervals[i];
    int bpm = 60000 / (sum / peakIntervalCount);

    if (bpm >= 40 && bpm <= 180) {
      currentBPM   = bpm;
      lastValidBPM = bpm;
    }
  }

  lastPeakTime = now;
}

void calculateSpO2() {
  long redAC = redMax - redMin;
  long irAC  = irMax  - irMin;

  if (redAC > 0 && irAC > 0 && redDC > 0 && irDC > 0) {
    float ratio = ((float)redAC / redDC) / ((float)irAC / irDC);
    int spo2 = constrain((int)(110 - 25 * ratio), 70, 100);
    currentSpO2   = spo2;
    lastValidSpO2 = spo2;
  }

  redMax = -100000; redMin = 100000;
  irMax  = -100000; irMin  = 100000;
}

int getDisplayBPM(unsigned long now) {
  if (fingerPresent && warmupDone && currentBPM >= 40) return currentBPM;
  if (!fingerPresent && lastValidBPM > 0 &&
      now - fingerLiftedTime < LAST_DATA_HOLD_MS) return lastValidBPM;
  return -1;
}

int getDisplaySpO2(unsigned long now) {
  if (fingerPresent && warmupDone && currentSpO2 > 0) return currentSpO2;
  if (!fingerPresent && lastValidSpO2 > 0 &&
      now - fingerLiftedTime < LAST_DATA_HOLD_MS) return lastValidSpO2;
  return -1;
}


// ===================================================================
// MODUL 3: HISTORY
// ===================================================================

void updateHistory(unsigned long now) {
  if (now - lastHistorySave < 1000) return;
  lastHistorySave = now;

  int bpm  = getDisplayBPM(now);
  int spo2 = getDisplaySpO2(now);

  if (bpm > 0 || spo2 > 0) {
    bpmHistory[historyIndex]  = bpm;
    spo2History[historyIndex] = spo2;
    historyIndex = (historyIndex + 1) % HISTORY_SIZE;
    if (historyCount < HISTORY_SIZE) historyCount++;
  }
}

int getAverageFromHistory(int history[]) {
  int sum = 0, count = 0;
  for (int i = 0; i < historyCount; i++) {
    if (history[i] > 0) { sum += history[i]; count++; }
  }
  return count > 0 ? sum / count : -1;
}


// ===================================================================
// MODUL 4: DISPLAY OLED
// ===================================================================
/*
 *  Layout 128x64:
 *  ┌──────────────────────────────┐
 *  │ Aktivitas    | Status jari   │  y=0  (textsize 1)
 *  ├──────────────────────────────┤  y=9
 *  │ HR: 75 bpm                   │  y=12 (textsize 2)
 *  │ SpO2: 98%                    │  y=30 (textsize 2)
 *  ├──────────────────────────────┤  y=48
 *  │ Avg 30dtk                    │  y=52 (textsize 1)
 *  └──────────────────────────────┘
 */

void updateDisplay(unsigned long now) {
  static unsigned long lastUpdate = 0;
  if (now - lastUpdate < 200) return;
  lastUpdate = now;

  if (fallAlertActive && now - fallAlertStart > FALL_DISPLAY_LOCK_MS) {
    fallAlertActive = false;
  }

  display.clearDisplay();
  if (fallAlertActive) {
    drawFallAlertScreen(now);
  } else {
    drawNormalScreen(now);
  }
  display.display();
}

void drawFallAlertScreen(unsigned long now) {
  unsigned long remaining = (FALL_DISPLAY_LOCK_MS - (now - fallAlertStart)) / 1000;

  display.drawRect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, SSD1306_WHITE);
  display.drawRect(2, 2, SCREEN_WIDTH-4, SCREEN_HEIGHT-4, SSD1306_WHITE);

  display.setTextSize(2);
  display.setCursor(10, 5);
  display.println("JATUH!");

  display.setTextSize(1);
  display.setCursor(10, 30);
  display.println("TERDETEKSI!");

  display.setCursor(10, 45);
  display.print("Reset dlm: ");
  display.print(remaining);
  display.println("s");
}

void drawNormalScreen(unsigned long now) {
  int avgBPM  = getAverageFromHistory(bpmHistory);
  int avgSpO2 = getAverageFromHistory(spo2History);
  int dispBPM  = getDisplayBPM(now);
  int dispSpO2 = getDisplaySpO2(now);

  // --- Baris atas: aktivitas (kiri) + status jari (kanan) ---
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print(getActivityLabel());

  // status jari di kanan
  String fingerStatus;
  if (!fingerPresent) {
    bool inHold = lastValidBPM > 0 && now - fingerLiftedTime < LAST_DATA_HOLD_MS;
    fingerStatus = inHold ? "Hold" : "No finger";
  } else if (!warmupDone) {
    unsigned long rem = (WARMUP_MS - (now - fingerDetectedTime)) / 1000 + 1;
    fingerStatus = "Warm " + String(rem) + "s";
  } else {
    fingerStatus = "OK";
  }

  // rata kanan
  int16_t x, y; uint16_t w, h;
  display.getTextBounds(fingerStatus, 0, 0, &x, &y, &w, &h);
  display.setCursor(SCREEN_WIDTH - w, 0);
  display.print(fingerStatus);

  // garis pemisah
  display.drawLine(0, 9, SCREEN_WIDTH, 9, SSD1306_WHITE);

  // --- HR (textsize 2) ---
  display.setTextSize(2);
  display.setCursor(0, 12);
  display.print("HR:");
  if (dispBPM > 0) {
    display.print(dispBPM);
    display.print("bpm");
  } else {
    display.print("--");
  }

  // --- SpO2 (textsize 2) ---
  display.setCursor(0, 30);
  display.print("O2:");
  if (dispSpO2 > 0) {
    display.print(dispSpO2);
    display.print("%");
  } else {
    display.print("--");
  }

  // garis bawah
  display.drawLine(0, 48, SCREEN_WIDTH, 48, SSD1306_WHITE);

  // --- Baris bawah: rata-rata 30 detik ---
  display.setTextSize(1);
  display.setCursor(0, 52);
  display.print("Avg30s HR:");
  display.print(avgBPM > 0 ? String(avgBPM) : "--");
  display.print(" O2:");
  display.print(avgSpO2 > 0 ? String(avgSpO2) : "--");
  display.print("%");
}