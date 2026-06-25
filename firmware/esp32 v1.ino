#include <WiFi.h>
#include <WiFiManager.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "MAX30105.h"
#include "heartRate.h" 
#include <PubSubClient.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ==================== KONFIGURASI SISTEM ====================
WiFiManager wifiManager;

// Broker MQTT 
const char* mqtt_broker      = "broker.hivemq.com"; 
const int mqtt_port          = 1883;
const char* mqtt_topic       = "neuroflow/device/data";
const char* mqtt_commands    = "neuroflow/device/commands";
const char* client_id        = "neuroflow_esp32_wristband";

// Konstanta Waktu & Threshold
const unsigned long CALIBRATION_MS     = 5000; 
const unsigned long SAMPLE_INTERVAL_MS = 20;   // 50Hz
const unsigned long TELEMETRY_INTERVAL = 1000; // 1 Detik
const unsigned long MQTT_RETRY_INTERVAL= 5000; // Coba ulang MQTT setiap 5 detik (Non-blocking)
const unsigned long IDLE_TIMEOUT_MS    = 5000; // 5 Menit (300.000 ms) untuk Deep Sleep

// --- Activity Detection (Tetap berjalan di background untuk MQTT) ---
#define ACTIVITY_WINDOW_SIZE  50    
#define STD_THRESHOLD_JALAN   0.06f 
#define STD_THRESHOLD_LARI    0.25f 

// --- Heart Rate (MAX30102) ---
#define IR_FINGER_THRESHOLD  30000
#define DC_ALPHA             0.85f
#define PEAK_MIN_INTERVAL_MS 400
#define PEAK_MAX_INTERVAL_MS 1500
#define PEAK_THRESHOLD       300
#define WARMUP_MS            8000
#define LAST_DATA_HOLD_MS    2000 // Telah diperbaiki dari typo sebelumnya
#define HISTORY_SIZE         30

// Inisialisasi bus I2C
TwoWire I2C_BUS = TwoWire(0);

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1

// Konfigurasi Baterai & Pin
const int BATTERY_PIN = 34;
const int MPU_INT_PIN = 33; // Pin Interrupt MPU6050 untuk Wakeup

const float BATTERY_VOLTAGE_MIN = 3.3;
const float BATTERY_VOLTAGE_MAX = 4.2;
const float VOLTAGE_DIVIDER_RATIO = 2.0;
const int ADC_MAX_VALUE = 4095;
const float ADC_REFERENCE = 3.3;
const float BATTERY_CALIBRATION_FACTOR = 1.133; 

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &I2C_BUS, OLED_RESET);
bool oledAvailable = false;

Adafruit_MPU6050 mpu;
MAX30105 maxSensor;
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// --- State Variables ---
enum ActivityLevel { ACTIVITY_DIAM, ACTIVITY_JALAN, ACTIVITY_LARI };
ActivityLevel currentActivity = ACTIVITY_DIAM;
float magBuffer[ACTIVITY_WINDOW_SIZE];
int magBufferIndex = 0;
bool magBufferFull = false;

long irDC = 0, redDC = 0;
bool dcInitialized = false;
long irFilteredPrev = 0;
long irPeakValue = 0;
bool irRising = false;
long lastPeakTime = 0;
long peakIntervals[5] = {0};
int peakIntervalIndex = 0;
int peakIntervalCount = 0;
int currentBPM = -1;
int currentSpO2 = -1;
int lastValidBPM = -1;
int lastValidSpO2 = -1;
long redMax = -100000, redMin = 100000;
long irMax = -100000, irMin = 100000;
bool fingerPresent = false;
bool warmupDone = false;
unsigned long fingerDetectedTime = 0;
unsigned long fingerLiftedTime = 0;

int bpmHistory[HISTORY_SIZE];
int spo2History[HISTORY_SIZE];
int historyIndex = 0;
int historyCount = 0;
unsigned long lastHistorySave = 0;

float baseGravityMag = 9.81; 
unsigned long lastSampleTime = 0;
unsigned long lastTelemetryTime = 0;
unsigned long lastMqttConnectAttempt = 0;
unsigned long lastActivityTime = 0; // Timer pelacakan aktivitas untuk Deep Sleep

bool alertsEnabled = true;
float tremorThreshold = 0.40;
int stressThreshold = 80;

const char* getActivityLabel() {
  switch (currentActivity) {
    case ACTIVITY_DIAM:  return "STATIONARY";
    case ACTIVITY_JALAN: return "WALKING";
    case ACTIVITY_LARI:  return "RUNNING";
    default:             return "STATIONARY";
  }
}

void oledPrintLines(const char* line1, const char* line2 = "", const char* line3 = "", const char* line4 = "") {
  if (!oledAvailable) return;
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(line1);
  if (line2[0]) display.println(line2);
  if (line3[0]) display.println(line3);
  if (line4[0]) display.println(line4);
  display.display();
}

void setupWiFi() {
  delay(10);
  Serial.println("\n[WiFi] Menghubungkan...");
  oledPrintLines("WiFi Status:", "Connecting...", "Check NeuroFlow-AP", "On Your Phone");

  WiFi.mode(WIFI_STA);
  wifiManager.setConfigPortalTimeout(180);

  if (!wifiManager.autoConnect("NeuroFlow-AP")) {
    Serial.println("\n[WiFi] Gagal, restart...");
    oledPrintLines("WiFi FAILED", "Restarting...", "", "");
    delay(3000);
    ESP.restart();
    return;
  }
  oledPrintLines("WiFi Connected!", WiFi.SSID().c_str(), WiFi.localIP().toString().c_str(), "");
  delay(1000);
}

void applyCommandSettings(const char* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  if (msg.indexOf("\"alerts_enabled\":false") >= 0 || msg.indexOf("\"alerts_enabled\": false") >= 0) alertsEnabled = false;
  else if (msg.indexOf("\"alerts_enabled\":true") >= 0 || msg.indexOf("\"alerts_enabled\": true") >= 0) alertsEnabled = true;

  int idx = msg.indexOf("\"tremor_threshold\":");
  if (idx >= 0) {
    float val = msg.substring(idx + 19).toFloat();
    if (val > 0.05 && val < 2.0) tremorThreshold = val;
  }
  idx = msg.indexOf("\"stress_threshold\":");
  if (idx >= 0) {
    int val = msg.substring(idx + 19, idx + 22).toInt();
    if (val >= 50 && val <= 100) stressThreshold = val;
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  if (String(topic) == mqtt_commands) applyCommandSettings((const char*)payload, length);
}

void handleMQTTConnection(unsigned long now) {
  if (!mqttClient.connected()) {
    if (now - lastMqttConnectAttempt >= MQTT_RETRY_INTERVAL) {
      lastMqttConnectAttempt = now;
      if (mqttClient.connect(client_id)) {
        mqttClient.subscribe(mqtt_commands);
      }
    }
  } else {
    mqttClient.loop();
  }
}

// ==================== TAMPILAN OLED BARU ====================
void oledShowMainScreen(const char* netStatus, float battVolt, int battPct, int hr, float tremor, int stress) {
  if (!oledAvailable) return;
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print(netStatus); 
  
  char battBuf[16];
  snprintf(battBuf, sizeof(battBuf), "%d%% %.1fV", battPct, battVolt);
  int16_t x, y; uint16_t w, h;
  display.getTextBounds(battBuf, 0, 0, &x, &y, &w, &h);
  display.setCursor(SCREEN_WIDTH - w, 0);
  display.print(battBuf);
  
  display.drawLine(0, 10, SCREEN_WIDTH, 10, SSD1306_WHITE);

  display.setCursor(0, 15);
  display.setTextSize(1);
  display.print("HEART RATE:");

  display.setCursor(0, 26);
  if (!fingerPresent) {
    display.setTextSize(1);
    display.print("-> Pasang Gelang <-");
  } else if (!warmupDone) {
    unsigned long elapsed = millis() - fingerDetectedTime;
    int remain = (WARMUP_MS > elapsed) ? ((WARMUP_MS - elapsed) / 1000) + 1 : 0;
    
    display.setTextSize(2);
    display.print("WARM: ");
    display.print(remain);
    display.print("s");
  } else {
    display.setTextSize(2);
    if (hr > 0) {
      display.print(hr);
      display.setTextSize(1);
      display.print(" BPM");
    } else {
      display.print("-- BPM");
    }
  }

  display.drawLine(0, 44, SCREEN_WIDTH, 44, SSD1306_WHITE);

  display.setTextSize(1);
  display.setCursor(0, 48);
  display.print("TREMOR");
  display.setCursor(0, 57);
  display.print(tremor, 2);

  display.setCursor(70, 48);
  display.print("STRESS");
  display.setCursor(70, 57);
  display.print(stress); 
  display.print(" %");

  display.display();
}

float readBatteryVoltage() {
  int raw = analogRead(BATTERY_PIN);
  return (raw / (float)ADC_MAX_VALUE) * ADC_REFERENCE * VOLTAGE_DIVIDER_RATIO * BATTERY_CALIBRATION_FACTOR;
}

int batteryPercent(float voltage) {
  int percent = (int)round(((voltage - BATTERY_VOLTAGE_MIN) / (BATTERY_VOLTAGE_MAX - BATTERY_VOLTAGE_MIN)) * 100.0);
  return constrain(percent, 0, 100);
}

// ===================== SENSOR UTILITIES =====================
float getAccelMagnitude() {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);
  float ax = a.acceleration.x / 9.81f;
  float ay = a.acceleration.y / 9.81f;
  float az = a.acceleration.z / 9.81f;
  return sqrt(ax*ax + ay*ay + az*az);
}

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
  magBuffer[magBufferIndex] = magnitude;
  magBufferIndex = (magBufferIndex + 1) % ACTIVITY_WINDOW_SIZE;
  if (magBufferIndex == 0) magBufferFull = true;
  float std = computeRollingStd();
  if (std > STD_THRESHOLD_LARI) currentActivity = ACTIVITY_LARI;
  else if (std > STD_THRESHOLD_JALAN) currentActivity = ACTIVITY_JALAN;
  else currentActivity = ACTIVITY_DIAM;
}

void registerPeak(unsigned long now) {
  long interval = now - lastPeakTime;
  if (lastPeakTime != 0 && interval > PEAK_MIN_INTERVAL_MS && interval < PEAK_MAX_INTERVAL_MS) {
    peakIntervals[peakIntervalIndex % 5] = interval;
    peakIntervalIndex++;
    if (peakIntervalCount < 5) peakIntervalCount++;
    long sum = 0;
    for (int i = 0; i < peakIntervalCount; i++) sum += peakIntervals[i];
    int bpm = 60000 / (sum / peakIntervalCount);
    if (bpm >= 40 && bpm <= 180) {
      currentBPM = bpm;
      lastValidBPM = bpm;
    }
  }
  lastPeakTime = now;
}

void calculateSpO2() {
  long redAC = redMax - redMin;
  long irAC = irMax - irMin;
  if (redAC > 0 && irAC > 0 && redDC > 0 && irDC > 0) {
    float ratio = ((float)redAC / redDC) / ((float)irAC / irDC);
    int spo2 = constrain((int)(110 - 25 * ratio), 70, 100);
    currentSpO2 = spo2;
    lastValidSpO2 = spo2;
  }
  redMax = -100000; redMin = 100000;
  irMax = -100000; irMin = 100000;
}

void updateVitals(unsigned long now) {
  if (!maxSensor.available()) {
    maxSensor.check();
    if (!maxSensor.available()) return;
  }
  long irValue = maxSensor.getIR();
  long redValue = maxSensor.getRed();
  maxSensor.nextSample();

  if (irValue < IR_FINGER_THRESHOLD) {
    if (fingerPresent) {
      fingerPresent = false;
      fingerLiftedTime = now;
    }
    return;
  }

  if (!fingerPresent) {
    fingerPresent = true;
    warmupDone = false;
    fingerDetectedTime = now;
    dcInitialized = false;
    peakIntervalCount = 0;
    peakIntervalIndex = 0;
    lastPeakTime = 0;
    currentBPM = -1;
    currentSpO2 = -1;
    irFilteredPrev = 0;
    irRising = false;
  }

  if (!dcInitialized) {
    irDC = irValue; redDC = redValue;
    dcInitialized = true;
  }

  irDC = (DC_ALPHA * irDC) + ((1 - DC_ALPHA) * irValue);
  redDC = (DC_ALPHA * redDC) + ((1 - DC_ALPHA) * redValue);

  long irFiltered = irValue - irDC;
  long redFiltered = redValue - redDC;

  if (!warmupDone) {
    if (now - fingerDetectedTime >= WARMUP_MS) warmupDone = true;
    return;
  }

  if (irFiltered > irFilteredPrev) {
    irRising = true;
    irPeakValue = irFiltered;
  } else if (irRising && irFiltered < irFilteredPrev) {
    irRising = false;
    if (irPeakValue > PEAK_THRESHOLD) registerPeak(now);
    irPeakValue = 0;
  }
  irFilteredPrev = irFiltered;

  redMax = max(redMax, redFiltered); redMin = min(redMin, redFiltered);
  irMax = max(irMax, irFiltered); irMin = min(irMin, irFiltered);

  static unsigned long lastSpo2Calc = 0;
  if (now - lastSpo2Calc >= 1000) {
    lastSpo2Calc = now;
    calculateSpO2();
  }
}

int getDisplayBPM(unsigned long now) {
  if (fingerPresent && warmupDone && currentBPM >= 40) return currentBPM;
  if (!fingerPresent && lastValidBPM > 0 && now - fingerLiftedTime < LAST_DATA_HOLD_MS) return lastValidBPM;
  return -1;
}

int getDisplaySpO2(unsigned long now) {
  if (fingerPresent && warmupDone && currentSpO2 > 0) return currentSpO2;
  if (!fingerPresent && lastValidSpO2 > 0 && now - fingerLiftedTime < LAST_DATA_HOLD_MS) return lastValidSpO2;
  return -1;
}

void updateHistory(unsigned long now) {
  if (now - lastHistorySave < 1000) return;
  lastHistorySave = now;
  int bpm = getDisplayBPM(now);
  int spo2 = getDisplaySpO2(now);
  if (bpm > 0 || spo2 > 0) {
    bpmHistory[historyIndex] = bpm;
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

void initHistoryBuffer() {
  for (int i = 0; i < HISTORY_SIZE; i++) { bpmHistory[i] = -1; spo2History[i] = -1; }
  for (int i = 0; i < ACTIVITY_WINDOW_SIZE; i++) magBuffer[i] = 1.0f;
}

void jalankanKalibrasi() {
  Serial.println("\n=== MEMULAI KALIBRASI MPU6050 ===");
  oledPrintLines("Kalibrasi MPU6050", "Harap Diam...", "Tunggu...", "5 Detik");
  
  float sumMag = 0;
  int sampleCount = 0;
  unsigned long startCalib = millis();
  
  while (millis() - startCalib < CALIBRATION_MS) {
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    float mag = sqrt(a.acceleration.x * a.acceleration.x + a.acceleration.y * a.acceleration.y + a.acceleration.z * a.acceleration.z);
    sumMag += mag;
    sampleCount++;
    delay(20);
  }
  baseGravityMag = sumMag / sampleCount;
  Serial.println("[Kalibrasi Selesai]");
}

// ==================== FUNGSI DEEP SLEEP ====================
void goToDeepSleep() {
  Serial.println("\n[DEEP SLEEP] Mempersiapkan perangkat untuk tidur...");
  
  // 1. Matikan Layar OLED
  if (oledAvailable) {
    display.clearDisplay();
    display.display();
    display.ssd1306_command(SSD1306_DISPLAYOFF);
  }
  
  // 2. Putuskan WiFi & Update Status MQTT
  if (mqttClient.connected()) {
    mqttClient.publish(mqtt_topic, "{\"device_status\":\"SLEEP\"}");
    mqttClient.disconnect();
  }
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  
  // 3. Matikan sensor MAX30102 untuk hemat daya
  maxSensor.shutDown();
  
  // 4. Konfigurasi Wake Up menggunakan MPU6050 (Pin 33)
  mpu.getMotionInterruptStatus(); // Bersihkan status interrupt yang lama
  esp_sleep_enable_ext0_wakeup((gpio_num_t)MPU_INT_PIN, 1); // 1 = Bangun jika sinyal HIGH
  
  Serial.println("[DEEP SLEEP] Tidur sekarang. Gerakkan gelang untuk membangunkan.");
  delay(100); 
  esp_deep_sleep_start();
}

// ==================== MAIN SETUP ====================
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  // Cek apakah bangun dari Deep Sleep karena pergerakan
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT0) {
    Serial.println("\n[WAKEUP] Bangun karena ada pergerakan!");
  }

  // Setup Pin untuk Interrupt Wakeup
  pinMode(MPU_INT_PIN, INPUT_PULLDOWN);

  analogReadResolution(12);
  analogSetPinAttenuation(BATTERY_PIN, ADC_11db);

  I2C_BUS.begin(21, 22, 400000);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("[OLED] GAGAL!");
    oledAvailable = false;
  } else {
    oledAvailable = true;
    display.clearDisplay();
    display.display();
  }

  if (!mpu.begin(0x68, &I2C_BUS)) {
    Serial.println("[MPU6050] GAGAL!");
    oledPrintLines("HARDWARE ERROR", "MPU6050 Disconnected", "Check I2C Pins", "SDA=21 SCL=22");
    while (1) delay(10);
  }
  
  // MPU6050 Base Config
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ); 

  // MPU6050 Motion Interrupt Config untuk Wakeup
  mpu.setHighPassFilter(MPU6050_HIGHPASS_0_63_HZ);
  mpu.setMotionDetectionThreshold(5); 
  mpu.setMotionDetectionDuration(20); 
  mpu.setInterruptPinLatch(true);     
  mpu.setInterruptPinPolarity(false);  
  mpu.setMotionInterrupt(true);

  if (!maxSensor.begin(I2C_BUS, 400000)) { 
    Serial.println("[MAX30102] GAGAL!");
    oledPrintLines("HARDWARE ERROR", "MAX30102 Disconnected", "Check I2C Connections", "");
    while (1) delay(10);
  }
  
  // Jika habis bangun tidur, pastikan sensor MAX30102 menyala kembali
  maxSensor.wakeUp();
  maxSensor.setup(60, 4, 2, 100, 411, 4096);
  maxSensor.setPulseAmplitudeRed(255); 
  maxSensor.setPulseAmplitudeGreen(0);  

  initHistoryBuffer();
  setupWiFi();
  
  mqttClient.setServer(mqtt_broker, mqtt_port);
  mqttClient.setCallback(mqttCallback);

  jalankanKalibrasi();
  
  lastActivityTime = millis(); // Reset timer saat mulai
}

// ==================== MAIN LOOP ====================
void loop() {
  unsigned long currentTime = millis();

  handleMQTTConnection(currentTime);

  // 1. BLOK DETEKSI TREMOR & AKTIVITAS (50Hz)
  if (currentTime - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = currentTime;
    float magnitude = getAccelMagnitude();
    updateActivityLevel(magnitude);
  }

  // 2. BLOK VITALS (MAX30102 Polling Asinkron)
  updateVitals(currentTime);

  // Reset Timer Idle jika ada aktivitas atau sensor disentuh
  if (fingerPresent || currentActivity != ACTIVITY_DIAM) {
    lastActivityTime = currentTime;
  }

  // 3. BLOK HISTORI DATA
  updateHistory(currentTime);

  // 4. BLOK TELEMETRI & METRIK DISPLAY (Setiap 1 Detik)
  if (currentTime - lastTelemetryTime >= TELEMETRY_INTERVAL) {
    lastTelemetryTime = currentTime;

    int displayBPM = getDisplayBPM(currentTime);
    int avgBPM = getAverageFromHistory(bpmHistory);

    if (displayBPM < 0) displayBPM = (avgBPM > 0) ? avgBPM : 0;

    int calculatedStress = map(displayBPM, 60, 110, 15, 85);
    calculatedStress = constrain(calculatedStress, 0, 100);

    float tremorIntensity = computeRollingStd();
    float batteryVolt = readBatteryVoltage();
    int batteryPct = batteryPercent(batteryVolt);

    // --- CEK KONDISI DEEP SLEEP ---
    // Kondisi A: Idle Timeout (Gelang Dilepas & Tidak Bergerak > 5 Menit)
    if (currentTime - lastActivityTime >= IDLE_TIMEOUT_MS) {
      Serial.println("\n[INFO] Perangkat idle terlalu lama.");
      goToDeepSleep();
    }
    
    // // Kondisi B: Baterai Kritis (< 5%)
    // if (batteryPct <= 5) {
    //   Serial.println("\n[WARNING] Baterai Kritis!");
    //   oledPrintLines("BATERAI HABIS", "Memasuki", "Sleep Mode", "");
    //   delay(2000);
    //   goToDeepSleep();
    // }
    // ------------------------------

    const char* networkLabel = mqttClient.connected() ? "MQTT OK" : "MQTT DISC";

    // Publikasi data telemetri 
    if (mqttClient.connected()) {
      String jsonPayload = "{";
      jsonPayload += "\"activity\":\"" + String(getActivityLabel()) + "\",";
      jsonPayload += "\"stress_level\":" + String(calculatedStress) + ",";
      jsonPayload += "\"heart_rate\":" + String(displayBPM) + ",";
      jsonPayload += "\"avg_bpm_30s\":" + String(avgBPM) + ",";
      jsonPayload += "\"spo2\":" + String(getDisplaySpO2(currentTime)) + ",";
      jsonPayload += "\"tremor_intensity\":" + String(tremorIntensity, 3) + ",";
      jsonPayload += "\"battery_pct\":" + String(batteryPct) + ",";
      jsonPayload += "\"device_status\":\"ACTIVE\"";
      jsonPayload += "}";
      mqttClient.publish(mqtt_topic, jsonPayload.c_str());
    }

    oledShowMainScreen(networkLabel, batteryVolt, batteryPct, displayBPM, tremorIntensity, calculatedStress);
  }
}