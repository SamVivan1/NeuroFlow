// =====================================================================================
// NEUROFLOW WRISTBAND — FIRMWARE v2 (Edge Processing Upgrade)
// =====================================================================================
// Perubahan dari versi sebelumnya:
//  1. FFT (arduinoFFT) pada MPU6050 -> mendeteksi puncak frekuensi 4-6Hz (tremor Parkinson)
//  2. RMSSD (HRV time-domain) pada MAX30102 -> estimasi stres yang lebih bermakna klinis
//     daripada sekadar mapping BPM
//  3. Dual-core FreeRTOS:
//       - Core 1 : akuisisi I2C (MPU6050 + MAX30102) & komputasi matematis berat (FFT/RMSSD)
//       - Core 0 : OLED, MQTT publish, dan logika panduan pernafasan (sensitif jeda)
//  4. Mode "Regulasi Pernafasan" otomatis: ketika stres tinggi ATAU tremor parkinsonian
//     terdeteksi, perangkat memandu pasien bernafas berirama (4s tarik / 6s buang =
//     6 nafas/menit, mendekati "frekuensi resonansi" yang dikenal memaksimalkan HRV)
//     lewat animasi OLED + getaran haptic.
//
// LIBRARY TAMBAHAN YANG HARUS DIINSTAL:
//  - arduinoFFT (by kosme / Enrique Condes) versi >= 2.0.0  -> via Library Manager
//
// CATATAN PENTING (harus ditulis di laporan/TA Anda):
//  - Ambang TREMOR_FFT_AMPLITUDE_THRESHOLD dan mapping RMSSD->stres di bawah ini bersifat
//    HEURISTIK awal. Untuk validitas klinis, idealnya dikalibrasi dengan data riil pasien
//    (rekam beberapa sesi, bandingkan dengan skala UPDRS / kuesioner stres standar).
//  - HAPTIC_PIN mengasumsikan motor vibrasi digerakkan lewat transistor/MOSFET driver,
//    BUKAN dihubungkan langsung ke GPIO (arus motor vibrasi biasanya > batas aman GPIO ESP32).
// =====================================================================================

#include <WiFi.h>
#include <WiFiManager.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "MAX30105.h"
#include "heartRate.h"
#include <PubSubClient.h>
#include <U8g2lib.h>
#include <arduinoFFT.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

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
const unsigned long SAMPLE_INTERVAL_MS = 20;   // 50Hz -> juga jadi sampling rate FFT
const unsigned long TELEMETRY_INTERVAL = 1000; // 1 Detik
const unsigned long MQTT_RETRY_INTERVAL= 5000;
const unsigned long IDLE_TIMEOUT_MS    = 10000;
const unsigned long OLED_REFRESH_MS    = 200;  // refresh tampilan (lebih cepat utk animasi nafas)

// Boot Button For Reset WiFi Settings
const int RESET_PIN = 0;

// --- Activity Detection (klasifikasi DIAM/JALAN/LARI, tetap dipakai sbg gating tremor) ---
#define ACTIVITY_WINDOW_SIZE  50
#define STD_THRESHOLD_JALAN   0.06f
#define STD_THRESHOLD_LARI    0.25f

// --- FFT Tremor Detection (BARU) ---
#define FFT_SAMPLES           128                 // harus pangkat 2
#define FFT_SAMPLING_FREQ     50.0                // Hz, samakan dgn SAMPLE_INTERVAL_MS
#define TREMOR_BAND_MIN_HZ    3.5f                 // batas bawah pita pencarian (longgar)
#define TREMOR_BAND_MAX_HZ    7.0f                 // batas atas pita pencarian (longgar)
#define TREMOR_PARKINSON_MIN_HZ 4.0f                // pita klinis tremor istirahat Parkinson
#define TREMOR_PARKINSON_MAX_HZ 6.0f
#define TREMOR_FFT_AMPLITUDE_THRESHOLD 1.5         // AMBANG AWAL — perlu dikalibrasi!
#define MAG_EMA_ALPHA          0.95f                // EMA utk memisahkan komponen AC (mirip ekstraksi AC PPG)

// --- Heart Rate (MAX30102) ---
#define IR_FINGER_THRESHOLD  30000
#define DC_ALPHA             0.85f
#define PEAK_MIN_INTERVAL_MS 400
#define PEAK_MAX_INTERVAL_MS 1500
#define PEAK_THRESHOLD       300
#define WARMUP_MS            8000
#define LAST_DATA_HOLD_MS    2000
#define HISTORY_SIZE         30
#define RR_BUFFER_SIZE       12     // buffer interval RR utk RMSSD (BARU, sebelumnya 5)

// Inisialisasi bus I2C
TwoWire I2C_BUS = TwoWire(0);

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1

// Konfigurasi Baterai & Pin
const int BATTERY_PIN = 34;
const int MPU_INT_PIN = 33;
const int HAPTIC_PIN  = 27;   // BARU: motor vibrasi (via driver transistor) utk cue nafas

const float BATTERY_VOLTAGE_MIN = 3.3;
const float BATTERY_VOLTAGE_MAX = 4.2;
const float VOLTAGE_DIVIDER_RATIO = 2.0;
const int ADC_MAX_VALUE = 4095;
const float ADC_REFERENCE = 3.3;
const float BATTERY_CALIBRATION_FACTOR = 1.133;

U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE, 22, 21);
bool oledAvailable = false;

Adafruit_MPU6050 mpu;
MAX30105 maxSensor;
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// --- FFT objek (arduinoFFT v2 API) ---
double vReal[FFT_SAMPLES];
double vImag[FFT_SAMPLES];
ArduinoFFT<double> FFT = ArduinoFFT<double>(vReal, vImag, FFT_SAMPLES, FFT_SAMPLING_FREQ);

float fftBuffer[FFT_SAMPLES];
int   fftBufferIndex = 0;
bool  fftBufferFull = false;
float magEMA = 1.0f;

// --- State Variables (dipakai HANYA di Core1Task, kecuali disalin ke SharedData) ---
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

long rrIntervals[RR_BUFFER_SIZE];      // BARU: dipakai utk RMSSD
unsigned long beatCounter = 0;
int rrCount = 0;

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
unsigned long lastOledRefresh = 0;
unsigned long lastMqttConnectAttempt = 0;
unsigned long lastActivityTime = 0;

bool alertsEnabled = true;
float tremorThreshold = 0.40;
int stressThreshold = 80;

// ==================== DATA BERSAMA ANTAR CORE (BARU) ====================
struct SharedData {
  int bpm = -1;
  int spo2 = -1;
  float rmssd = -1;              // ms
  int stressLevel = -1;          // 0-100, gabungan RMSSD + BPM
  float tremorIntensity = 0;     // rolling std (gerakan kasar, existing)
  float tremorFreqHz = 0;        // puncak frekuensi FFT
  bool parkinsonianTremor = false;
  ActivityLevel activity = ACTIVITY_DIAM;
  bool fingerPresent = false;
  bool warmupDone = false;
};
SharedData sharedData;
SemaphoreHandle_t dataMutex;   // melindungi SharedData
SemaphoreHandle_t i2cMutex;    // melindungi bus I2C (dipakai sensor DAN OLED, satu bus fisik!)

TaskHandle_t core1TaskHandle = NULL;
TaskHandle_t core0TaskHandle = NULL;

// ==================== MODE REGULASI PERNAFASAN (BARU) ====================
enum BreathPhase { BREATH_INHALE, BREATH_EXHALE };
bool breathingSessionActive = false;
unsigned long breathingSessionStart = 0;
unsigned long breathPhaseStart = 0;
BreathPhase breathPhase = BREATH_INHALE;
unsigned long lastBreathingRecheck = 0;

// 4 detik tarik nafas, 6 detik buang nafas -> siklus 10s = 6 nafas/menit
// (mendekati frekuensi resonansi pernafasan yang umum dipakai pada biofeedback HRV)
const unsigned long BREATH_INHALE_MS      = 4000;
const unsigned long BREATH_EXHALE_MS      = 6000;
const unsigned long BREATHING_MIN_SESSION_MS = 120000; // minimal 2 menit per sesi
const unsigned long BREATHING_RECHECK_MS  = 10000;     // cek perbaikan kondisi tiap 10s

void configModeCallback(WiFiManager *myWiFiManager);
float mapFloat(float x, float in_min, float in_max, float out_min, float out_max);

const char* getActivityLabel(ActivityLevel act) {
  switch (act) {
    case ACTIVITY_DIAM:  return "STATIONARY";
    case ACTIVITY_JALAN: return "WALKING";
    case ACTIVITY_LARI:  return "RUNNING";
    default:             return "STATIONARY";
  }
}

void oledPrintLines(const char* line1, const char* line2 = "", const char* line3 = "", const char* line4 = "") {
  if (!oledAvailable) return;
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_7x14_tr);
  u8g2.drawStr(0, 12, line1);
  if (line2[0]) u8g2.drawStr(0, 26, line2);
  if (line3[0]) u8g2.drawStr(0, 40, line3);
  if (line4[0]) u8g2.drawStr(0, 54, line4);
  u8g2.sendBuffer();
}

void drawWifiIcon(int x, int y, bool connected) {
  u8g2.drawPixel(x + 8, y + 12);
  u8g2.drawLine(x + 6, y + 10, x + 10, y + 10);
  u8g2.drawLine(x + 5, y + 8,  x + 11, y + 8);
  u8g2.drawLine(x + 3, y + 6,  x + 13, y + 6);
  u8g2.drawLine(x + 1, y + 4,  x + 15, y + 4);
  if (!connected) {
    u8g2.drawLine(x + 2, y + 14, x + 14, y + 2);
  }
}

void drawBatteryIcon(int x, int y, int pct) {
  u8g2.drawFrame(x, y, 18, 9);
  u8g2.drawBox(x + 18, y + 2, 2, 4);
  int bars = map(constrain(pct,0,100),0,100,0,4);
  if (bars >= 1) u8g2.drawBox(x+2 ,y+2,3,5);
  if (bars >= 2) u8g2.drawBox(x+6 ,y+2,3,5);
  if (bars >= 3) u8g2.drawBox(x+10,y+2,3,5);
  if (bars >= 4) u8g2.drawBox(x+14,y+2,2,5);
}

void drawHeartIcon(int x,int y){
  u8g2.drawDisc(x+3,y+3,3);
  u8g2.drawDisc(x+9,y+3,3);
  u8g2.drawTriangle(x,y+4,x+12,y+4,x+6,y+12);
}

void drawActivityIcon(int x, int y, ActivityLevel act) {
  switch (act) {
    case ACTIVITY_DIAM: u8g2.drawDisc(x + 4, y + 4, 3); break;
    case ACTIVITY_JALAN:
      u8g2.drawCircle(x + 4, y + 2, 2);
      u8g2.drawLine(x + 4, y + 4, x + 4, y + 9);
      u8g2.drawLine(x + 4, y + 6, x + 1, y + 8);
      u8g2.drawLine(x + 4, y + 6, x + 7, y + 5);
      u8g2.drawLine(x + 4, y + 9, x + 2, y + 12);
      u8g2.drawLine(x + 4, y + 9, x + 7, y + 12);
      break;
    case ACTIVITY_LARI:
      u8g2.drawCircle(x + 4, y + 2, 2);
      u8g2.drawLine(x + 4, y + 4, x + 7, y + 7);
      u8g2.drawLine(x + 7, y + 7, x + 10, y + 5);
      u8g2.drawLine(x + 7, y + 7, x + 5, y + 11);
      u8g2.drawLine(x + 5, y + 11, x + 2, y + 13);
      u8g2.drawLine(x + 5, y + 11, x + 9, y + 13);
      break;
  }
}

void configModeCallback(WiFiManager *myWiFiManager)
{
  if (!oledAvailable) return;
  u8g2.clearBuffer();
  drawWifiIcon(56,10,false);
  u8g2.setFont(u8g2_font_6x10_tr);
  u8g2.drawStr(34,38,"SETUP WIFI");
  u8g2.setFont(u8g2_font_5x7_tr);
  u8g2.drawStr(28,52,"NeuroFlow-AP");
  u8g2.sendBuffer();
}

void setupWiFi() {
  delay(10);
  Serial.println("\n[WiFi] Menghubungkan...");
  if(oledAvailable){
    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_logisoso16_tf);
    u8g2.drawStr(18,28,"Neuro");
    u8g2.drawStr(42,52,"Flow");
    u8g2.sendBuffer();
    delay(1000);

    u8g2.clearBuffer();
    drawWifiIcon(56,18,false);
    u8g2.setFont(u8g2_font_6x10_tr);
    u8g2.drawStr(34,54,"CONNECTING");
    u8g2.sendBuffer();
}

  WiFi.mode(WIFI_STA);
  wifiManager.setConfigPortalTimeout(180);
  wifiManager.setAPCallback(configModeCallback);

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

// --- Deklarasi maju (dipakai sebelum didefinisikan) ---
void startBreathingSession(unsigned long now);
void stopBreathingSession();

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

  // BARU: kontrol manual sesi pernafasan, misal dipicu dari app/clinician dashboard
  if (msg.indexOf("\"start_breathing\":true") >= 0) startBreathingSession(millis());
  if (msg.indexOf("\"stop_breathing\":true") >= 0) stopBreathingSession();
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

// ==================== TAMPILAN OLED — LAYAR UTAMA ====================
void oledShowMainScreen(const char* netStatus,float battVolt,int battPct,int hr,float tremor,int stress, ActivityLevel act, bool fingerOn, bool warmup) {
  if (!oledAvailable) return;
  u8g2.clearBuffer();
  bool connected = (strcmp(netStatus,"MQTT OK")==0);
  drawWifiIcon(2,0,connected);
  drawBatteryIcon(105,3,battPct);
  char battStr[8];
  sprintf(battStr,"%d%%",battPct);
  u8g2.setFont(u8g2_font_5x7_tr);
  u8g2.drawStr(78,11,battStr);
  u8g2.drawHLine(0,18,128);
  if (!fingerOn) {
      drawHeartIcon(55,23);
      u8g2.setFont(u8g2_font_6x10_tr);
      u8g2.drawStr(35,50,"NO SIGNAL");
  } else if (!warmup) {
      unsigned long elapsed = millis()-fingerDetectedTime;
      int remain = (WARMUP_MS > elapsed) ? ((WARMUP_MS-elapsed)/1000)+1 : 0;
      char txt[8]; sprintf(txt,"%d",remain);
      u8g2.setFont(u8g2_font_logisoso24_tf);
      int w=u8g2.getStrWidth(txt);
      u8g2.drawStr((128-w)/2,48,txt);
  } else {
      char bpmStr[8];
      if(hr>0) sprintf(bpmStr,"%d",hr); else strcpy(bpmStr,"--");
      drawHeartIcon(25,24);
      u8g2.setFont(u8g2_font_logisoso24_tf);
      u8g2.drawStr(48,48,bpmStr);
      u8g2.setFont(u8g2_font_5x7_tr);
      u8g2.drawStr(50,60,"BPM");
  }
  drawActivityIcon(112,22, act);
  u8g2.drawHLine(0,54,128);
  char tremorStr[12]; sprintf(tremorStr,"T %.2f",tremor);
  u8g2.setFont(u8g2_font_5x7_tr);
  u8g2.drawStr(2,63,tremorStr);
  char stressStr[12];
  if (stress >= 0) sprintf(stressStr,"S %d%%",stress); else sprintf(stressStr,"S --");
  u8g2.drawStr(92,63,stressStr);
  u8g2.sendBuffer();
}

// ==================== TAMPILAN OLED — MODE REGULASI PERNAFASAN (BARU) ====================
void renderBreathingScreen(unsigned long now) {
  if (!oledAvailable) return;
  unsigned long phaseElapsed  = now - breathPhaseStart;
  unsigned long phaseDuration = (breathPhase == BREATH_INHALE) ? BREATH_INHALE_MS : BREATH_EXHALE_MS;
  float progress = (float)phaseElapsed / (float)phaseDuration;
  if (progress > 1.0f) progress = 1.0f;

  const int minR = 8, maxR = 28;
  int radius = (breathPhase == BREATH_INHALE)
                 ? minR + (int)((maxR - minR) * progress)
                 : maxR - (int)((maxR - minR) * progress);
  if (radius < 2) radius = 2;

  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_5x7_tr);
  u8g2.drawStr(2, 9, "MODE TENANG");

  u8g2.drawCircle(64, 34, radius);
  if (radius > 4) u8g2.drawCircle(64, 34, radius - 3);

  const char* label = (breathPhase == BREATH_INHALE) ? "TARIK NAFAS" : "BUANG NAFAS";
  u8g2.setFont(u8g2_font_6x10_tr);
  int w = u8g2.getStrWidth(label);
  u8g2.drawStr((128 - w) / 2, 58, label);

  long remainMs = (long)phaseDuration - (long)phaseElapsed;
  int remainSec = (remainMs > 0) ? (remainMs / 1000) + 1 : 0;
  char secStr[4]; sprintf(secStr, "%d", remainSec);
  u8g2.drawStr(118, 9, secStr);

  u8g2.sendBuffer();
}

float readBatteryVoltage() {
  int raw = analogRead(BATTERY_PIN);
  return (raw / (float)ADC_MAX_VALUE) * ADC_REFERENCE * VOLTAGE_DIVIDER_RATIO * BATTERY_CALIBRATION_FACTOR;
}

int batteryPercent(float voltage) {
  int percent = (int)round(((voltage - BATTERY_VOLTAGE_MIN) / (BATTERY_VOLTAGE_MAX - BATTERY_VOLTAGE_MIN)) * 100.0);
  return constrain(percent, 0, 100);
}

float mapFloat(float x, float in_min, float in_max, float out_min, float out_max) {
  if (in_max == in_min) return out_min;
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

// ===================== SENSOR UTILITIES (MPU6050) =====================
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

// ===================== FFT TREMOR DETECTION (BARU) =====================
// Ekstrak komponen AC dari magnitudo akselerasi (EMA sbg baseline gravitasi/gerakan lambat),
// mirip teknik ekstraksi AC yang sudah dipakai pada sinyal PPG MAX30102.
void collectFFTSample(float magnitude) {
  magEMA = MAG_EMA_ALPHA * magEMA + (1.0f - MAG_EMA_ALPHA) * magnitude;
  float acComponent = magnitude - magEMA;
  fftBuffer[fftBufferIndex++] = acComponent;
  if (fftBufferIndex >= FFT_SAMPLES) {
    fftBufferIndex = 0;
    fftBufferFull = true;
  }
}

// Mencari puncak frekuensi HANYA pada pita pencarian tremor (3.5-7Hz),
// lalu menandai sebagai "tremor parkinsonian" jika puncaknya jatuh di pita klinis 4-6Hz
// DAN amplitudonya melewati ambang DAN tangan sedang relatif diam (gating ACTIVITY_DIAM)
// — karena tremor istirahat Parkinson paling bermakna diukur saat anggota tubuh tidak
// sengaja digerakkan (bukan saat berjalan/berlari).
void computeTremorFFT(SharedData &out) {
  for (int i = 0; i < FFT_SAMPLES; i++) { vReal[i] = fftBuffer[i]; vImag[i] = 0; }

  FFT.windowing(FFTWindow::Hamming, FFTDirection::Forward);
  FFT.compute(FFTDirection::Forward);
  FFT.complexToMagnitude();

  double freqResolution = FFT_SAMPLING_FREQ / FFT_SAMPLES; // ~0.39 Hz / bin
  int binMin = (int)(TREMOR_BAND_MIN_HZ / freqResolution);
  int binMax = (int)(TREMOR_BAND_MAX_HZ / freqResolution);
  if (binMax >= FFT_SAMPLES / 2) binMax = (FFT_SAMPLES / 2) - 1;

  double peakMag = 0; int peakBin = 0;
  for (int i = binMin; i <= binMax; i++) {
    if (vReal[i] > peakMag) { peakMag = vReal[i]; peakBin = i; }
  }
  float peakFreq = peakBin * freqResolution;

  out.tremorFreqHz = peakFreq;
  out.parkinsonianTremor = (peakMag > TREMOR_FFT_AMPLITUDE_THRESHOLD)
                            && (peakFreq >= TREMOR_PARKINSON_MIN_HZ && peakFreq <= TREMOR_PARKINSON_MAX_HZ)
                            && (out.activity == ACTIVITY_DIAM);

  fftBufferFull = false; // siap mengisi window berikutnya
}

// ===================== HEART RATE & RMSSD (BARU) =====================
void registerPeak(unsigned long now) {
  long interval = now - lastPeakTime;
  if (lastPeakTime != 0 && interval > PEAK_MIN_INTERVAL_MS && interval < PEAK_MAX_INTERVAL_MS) {
    rrIntervals[beatCounter % RR_BUFFER_SIZE] = interval;
    beatCounter++;
    if (rrCount < RR_BUFFER_SIZE) rrCount++;

    // BPM sesaat dirata-rata dari 5 RR terakhir (responsif, sama spt versi sebelumnya)
    int n = min(rrCount, 5);
    long sum = 0;
    for (int i = 0; i < n; i++) {
      long idx = (beatCounter - 1 - i + RR_BUFFER_SIZE) % RR_BUFFER_SIZE;
      sum += rrIntervals[idx];
    }
    int bpm = 60000 / (sum / n);
    if (bpm >= 40 && bpm <= 180) {
      currentBPM = bpm;
      lastValidBPM = bpm;
    }
  }
  lastPeakTime = now;
}

// RMSSD = root mean square of successive RR-interval differences.
// Metrik time-domain HRV standar; RMSSD rendah berkorelasi dgn dominansi simpatis (stres),
// RMSSD tinggi berkorelasi dgn dominansi parasimpatis (tenang/relaks).
float computeRMSSD() {
  if (rrCount < 3) return -1;
  int startLogical = (int)beatCounter - rrCount; // indeks logis RR tertua dlm window
  double sumSqDiff = 0;
  int diffs = 0;
  long prevVal = 0;
  bool havePrev = false;
  for (int i = 0; i < rrCount; i++) {
    long logicalIdx = startLogical + i;
    long val = rrIntervals[((logicalIdx % RR_BUFFER_SIZE) + RR_BUFFER_SIZE) % RR_BUFFER_SIZE];
    if (havePrev) {
      double d = (double)(val - prevVal);
      sumSqDiff += d * d;
      diffs++;
    }
    prevVal = val;
    havePrev = true;
  }
  if (diffs == 0) return -1;
  return sqrt(sumSqDiff / diffs);
}

// Estimasi stres gabungan: RMSSD (bobot dominan, lebih bermakna klinis) + level BPM (pendukung).
// Range RMSSD 15-80ms & BPM 60-110 adalah asumsi awal yg LAYAK DIKALIBRASI per-individu.
int computeStressLevel(float rmssd, int bpm) {
  int stressFromHRV = -1;
  if (rmssd >= 0) {
    float r = constrain(rmssd, 15.0f, 80.0f);
    stressFromHRV = (int)mapFloat(r, 15.0f, 80.0f, 90.0f, 10.0f); // RMSSD rendah -> stres tinggi
  }
  int stressFromBPM = -1;
  if (bpm > 0) {
    stressFromBPM = map(constrain(bpm, 60, 110), 60, 110, 15, 85);
  }
  if (stressFromHRV >= 0 && stressFromBPM >= 0) {
    return constrain((int)round(0.7 * stressFromHRV + 0.3 * stressFromBPM), 0, 100);
  } else if (stressFromHRV >= 0) {
    return stressFromHRV;
  } else if (stressFromBPM >= 0) {
    return stressFromBPM;
  }
  return -1;
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
    rrCount = 0;
    beatCounter = 0;
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
  for (int i = 0; i < FFT_SAMPLES; i++) fftBuffer[i] = 0.0f;
}

void jalankanKalibrasi() {
  Serial.println("\n=== MEMULAI KALIBRASI MPU6050 ===");
  if(oledAvailable){
    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_logisoso18_tf);
    u8g2.drawStr(54,42,"5");
    u8g2.setFont(u8g2_font_6x10_tr);
    u8g2.drawStr(36,58,"CALIBRATE");
    u8g2.sendBuffer();
  }

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

// ==================== MODE REGULASI PERNAFASAN — LOGIKA (BARU) ====================
void startBreathingSession(unsigned long now) {
  if (breathingSessionActive) return;
  breathingSessionActive = true;
  breathingSessionStart = now;
  breathPhase = BREATH_INHALE;
  breathPhaseStart = now;
  lastBreathingRecheck = now;
  Serial.println("[BREATHING] Sesi regulasi nafas dimulai.");
}

void stopBreathingSession() {
  if (!breathingSessionActive) return;
  breathingSessionActive = false;
  digitalWrite(HAPTIC_PIN, LOW);
  Serial.println("[BREATHING] Sesi regulasi nafas selesai.");
}

// Dipanggil tiap iterasi Core0Task (granularitas ~20ms) agar transisi fase nafas & haptic responsif.
void updateBreathingGuidance(unsigned long now, const SharedData &snap) {
  if (!breathingSessionActive) {
    bool needGuidance = alertsEnabled && ((snap.stressLevel >= stressThreshold) || snap.parkinsonianTremor);
    if (needGuidance) startBreathingSession(now);
    return;
  }

  unsigned long phaseElapsed = now - breathPhaseStart;
  if (breathPhase == BREATH_INHALE) {
    digitalWrite(HAPTIC_PIN, HIGH); // getar selama menarik nafas (cue ritme)
    if (phaseElapsed >= BREATH_INHALE_MS) {
      breathPhase = BREATH_EXHALE;
      breathPhaseStart = now;
    }
  } else {
    digitalWrite(HAPTIC_PIN, LOW); // diam selama membuang nafas
    if (phaseElapsed >= BREATH_EXHALE_MS) {
      breathPhase = BREATH_INHALE;
      breathPhaseStart = now;
    }
  }

  if (now - lastBreathingRecheck >= BREATHING_RECHECK_MS) {
    lastBreathingRecheck = now;
    bool improved = (snap.stressLevel >= 0 && snap.stressLevel < stressThreshold - 10) && !snap.parkinsonianTremor;
    if (improved && (now - breathingSessionStart >= BREATHING_MIN_SESSION_MS)) {
      stopBreathingSession();
    }
  }
}

// ==================== FUNGSI DEEP SLEEP ====================
void goToDeepSleep() {
  Serial.println("\n[DEEP SLEEP] Mempersiapkan perangkat untuk tidur...");

  if (oledAvailable) {
    u8g2.clearBuffer();
    u8g2.sendBuffer();
    u8g2.setPowerSave(1);
  }

  if (mqttClient.connected()) {
    mqttClient.publish(mqtt_topic, "{\"device_status\":\"SLEEP\"}");
    mqttClient.disconnect();
  }
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);

  digitalWrite(HAPTIC_PIN, LOW);
  maxSensor.shutDown();

  mpu.getMotionInterruptStatus();
  esp_sleep_enable_ext0_wakeup((gpio_num_t)MPU_INT_PIN, 1);

  Serial.println("[DEEP SLEEP] Tidur sekarang. Gerakkan gelang untuk membangunkan.");
  delay(100);
  esp_deep_sleep_start();
}

// ==================== TELEMETRI MQTT (BARU, dipisah dari loop) ====================
void publishTelemetry(const SharedData &snap, int avgBpm, int battPct) {
  if (!mqttClient.connected()) return;
  String json = "{";
  json += "\"activity\":\"" + String(getActivityLabel(snap.activity)) + "\",";
  json += "\"stress_level\":" + String(snap.stressLevel) + ",";
  json += "\"heart_rate\":" + String(snap.bpm) + ",";
  json += "\"avg_bpm_30s\":" + String(avgBpm) + ",";
  json += "\"spo2\":" + String(snap.spo2) + ",";
  json += "\"rmssd_ms\":" + String(snap.rmssd, 1) + ",";
  json += "\"tremor_intensity\":" + String(snap.tremorIntensity, 3) + ",";
  json += "\"tremor_freq_hz\":" + String(snap.tremorFreqHz, 2) + ",";
  json += "\"parkinsonian_tremor\":" + String(snap.parkinsonianTremor ? "true" : "false") + ",";
  json += "\"breathing_session_active\":" + String(breathingSessionActive ? "true" : "false") + ",";
  json += "\"breathing_phase\":\"" + String(breathingSessionActive ? (breathPhase == BREATH_INHALE ? "INHALE" : "EXHALE") : "NONE") + "\",";
  json += "\"battery_pct\":" + String(battPct) + ",";
  json += "\"device_status\":\"ACTIVE\"";
  json += "}";
  mqttClient.publish(mqtt_topic, json.c_str());
}

// =====================================================================================
// CORE 1 TASK — Akuisisi sensor (I2C) + komputasi matematis berat (FFT, RMSSD)
// Sengaja TIDAK menyentuh OLED/WiFi/MQTT supaya pekerjaan berat ini tidak pernah
// membuat tampilan atau koneksi jaringan "macet" sesaat (non-blocking secara desain).
// =====================================================================================
void Core1Task(void *pvParameters) {
  unsigned long localLastSample = millis();
  for (;;) {
    unsigned long now = millis();

    // --- Sampling MPU6050 @ 50Hz: aktivitas + buffer FFT ---
    if (now - localLastSample >= SAMPLE_INTERVAL_MS) {
      localLastSample = now;

      xSemaphoreTake(i2cMutex, portMAX_DELAY);
      float magnitude = getAccelMagnitude();
      xSemaphoreGive(i2cMutex);

      updateActivityLevel(magnitude);
      collectFFTSample(magnitude);

      SharedData localCopy;
      xSemaphoreTake(dataMutex, portMAX_DELAY);
      localCopy = sharedData;
      xSemaphoreGive(dataMutex);

      localCopy.activity = currentActivity;
      localCopy.tremorIntensity = computeRollingStd();

      if (fftBufferFull) {
        computeTremorFFT(localCopy); // FFT 128-titik, komputasi "berat" — aman di Core 1
      }

      xSemaphoreTake(dataMutex, portMAX_DELAY);
      sharedData.activity = localCopy.activity;
      sharedData.tremorIntensity = localCopy.tremorIntensity;
      sharedData.tremorFreqHz = localCopy.tremorFreqHz;
      sharedData.parkinsonianTremor = localCopy.parkinsonianTremor;
      xSemaphoreGive(dataMutex);
    }

    // --- Polling MAX30102 (non-blocking, internal sudah berbasis FIFO check) ---
    xSemaphoreTake(i2cMutex, portMAX_DELAY);
    updateVitals(now);
    xSemaphoreGive(i2cMutex);

    int dispBPM  = getDisplayBPM(now);
    int dispSpO2 = getDisplaySpO2(now);
    float rmssd  = computeRMSSD();
    int stress   = computeStressLevel(rmssd, dispBPM);

    xSemaphoreTake(dataMutex, portMAX_DELAY);
    sharedData.bpm = dispBPM;
    sharedData.spo2 = dispSpO2;
    sharedData.rmssd = rmssd;
    sharedData.stressLevel = stress;
    sharedData.fingerPresent = fingerPresent;
    sharedData.warmupDone = warmupDone;
    xSemaphoreGive(dataMutex);

    updateHistory(now);

    vTaskDelay(pdMS_TO_TICKS(2)); // beri jeda kecil agar watchdog & scheduler tetap sehat
  }
}

// =====================================================================================
// CORE 0 TASK — OLED, koneksi MQTT, panduan pernafasan (semua hal sensitif-jeda/UI)
// =====================================================================================
void Core0Task(void *pvParameters) {
  for (;;) {
    unsigned long now = millis();

    if (digitalRead(RESET_PIN) == LOW) {
      Serial.println("\n[INFO] Reset WiFi diperintahkan...");
      wifiManager.resetSettings();
      ESP.restart();
    }

    handleMQTTConnection(now);

    SharedData snap;
    xSemaphoreTake(dataMutex, portMAX_DELAY);
    snap = sharedData;
    xSemaphoreGive(dataMutex);

    if (snap.fingerPresent || snap.activity != ACTIVITY_DIAM) lastActivityTime = now;

    updateBreathingGuidance(now, snap);

    float battVolt = readBatteryVoltage();
    int battPct = batteryPercent(battVolt);

    if (now - lastActivityTime >= IDLE_TIMEOUT_MS) {
      Serial.println("\n[INFO] Perangkat idle terlalu lama.");
      goToDeepSleep();
    }

    if (now - lastTelemetryTime >= TELEMETRY_INTERVAL) {
      lastTelemetryTime = now;
      int avgBpm = getAverageFromHistory(bpmHistory);
      publishTelemetry(snap, avgBpm, battPct);
    }

    if (now - lastOledRefresh >= OLED_REFRESH_MS) {
      lastOledRefresh = now;
      xSemaphoreTake(i2cMutex, portMAX_DELAY);
      if (breathingSessionActive) {
        renderBreathingScreen(now);
      } else {
        const char* networkLabel = mqttClient.connected() ? "MQTT OK" : "MQTT DISC";
        oledShowMainScreen(networkLabel, battVolt, battPct, snap.bpm, snap.tremorIntensity,
                           snap.stressLevel, snap.activity, snap.fingerPresent, snap.warmupDone);
      }
      xSemaphoreGive(i2cMutex);
    }

    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

// ==================== MAIN SETUP ====================
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  pinMode(RESET_PIN, INPUT_PULLUP);
  pinMode(HAPTIC_PIN, OUTPUT);
  digitalWrite(HAPTIC_PIN, LOW);

  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT0) {
    Serial.println("\n[WAKEUP] Bangun karena ada pergerakan!");
  }

  pinMode(MPU_INT_PIN, INPUT_PULLDOWN);

  analogReadResolution(12);
  analogSetPinAttenuation(BATTERY_PIN, ADC_11db);

  I2C_BUS.begin(21, 22, 400000);

  if (!u8g2.begin()) {
    Serial.println("[OLED] GAGAL!");
    oledAvailable = false;
  } else {
    oledAvailable = true;
    u8g2.clearBuffer();
    u8g2.sendBuffer();
  }

  if (!mpu.begin(0x68, &I2C_BUS)) {
    Serial.println("[MPU6050] GAGAL!");
    oledPrintLines("HARDWARE ERROR", "MPU6050 Disconnected", "Check I2C Pins", "SDA=21 SCL=22");
    while (1) delay(10);
  }

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

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

  maxSensor.wakeUp();
  maxSensor.setup(60, 4, 2, 100, 411, 4096);
  maxSensor.setPulseAmplitudeRed(255);
  maxSensor.setPulseAmplitudeGreen(0);

  initHistoryBuffer();
  setupWiFi();

  mqttClient.setServer(mqtt_broker, mqtt_port);
  mqttClient.setCallback(mqttCallback);

  jalankanKalibrasi();

  lastActivityTime = millis();
  lastTelemetryTime = millis();
  lastOledRefresh = millis();

  // --- BARU: buat mutex & jalankan dua task pada masing-masing core ---
  dataMutex = xSemaphoreCreateMutex();
  i2cMutex  = xSemaphoreCreateMutex();

  xTaskCreatePinnedToCore(Core1Task, "Core1_Sensors",     8192, NULL, 1, &core1TaskHandle, 1);
  xTaskCreatePinnedToCore(Core0Task, "Core0_DisplayMQTT", 8192, NULL, 1, &core0TaskHandle, 0);
}

// ==================== MAIN LOOP ====================
// Pekerjaan utama sudah dipindah ke Core1Task & Core0Task; loop() Arduino dibiarkan idle.
void loop() {
  vTaskDelay(pdMS_TO_TICKS(1000));
}
