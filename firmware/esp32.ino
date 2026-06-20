#include <WiFi.h>
#include <WiFiManager.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "MAX30105.h"
#include "heartRate.h" // Library bawaan SparkFun untuk pendeteksi detak jantung
#include <PubSubClient.h>

// ==================== KONFIGURASI SISTEM ====================
// Kredensial Wi-Fi sekarang disimpan oleh WiFiManager, tidak hardcoded.
WiFiManager wifiManager;

// Broker MQTT (Sesuaikan dengan backend Firebase/AWS/Public Broker Anda)
const char* mqtt_broker      = "broker.hivemq.com"; 
const int mqtt_port          = 1883;
const char* mqtt_topic       = "neuroflow/device/data";
const char* mqtt_commands    = "neuroflow/device/commands";
const char* client_id        = "neuroflow_esp32_wristband";

// Pinout Aktuator Haptic & Indikator (Sesuai Rancangan Mekanis)
const int HAPTIC_PIN         = 25; // Pin transistor NPN penggerak motor getar

// Konstanta Waktu & Threshold (Sesuai Parameter Desain)
const unsigned long CALIBRATION_MS     = 5000; // Durasi kalibrasi awal (5 detik)
const unsigned long SAMPLE_INTERVAL_MS = 20;   // Frekuensi sampling sensor (50Hz)
const unsigned long TELEMETRY_INTERVAL = 1000; // Interval publish MQTT (1 detik)

const float ALARM_TREMOR_THRESHOLD     = 0.40; // Batas amplitudo tremor mendeteksi Parkinson
// ============================================================

// Inisialisasi Dua Jalur Bus I2C Fisik Terpisah
TwoWire I2C_MPU = TwoWire(0);   
TwoWire I2C_MAX = TwoWire(1);   

Adafruit_MPU6050 mpu;
MAX30105 maxSensor;
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Variabel Kalibrasi & Filter Tremor
float baseGravityMag = 9.81; 
unsigned long lastSampleTime = 0;

// Variabel Detak Jantung (MAX30102)
long lastBeat = 0; 
float beatsPerMinute = 0;
int beatAvg = 75; // Nilai default awal sebelum pembacaan stabil

// Variabel Waktu Telemetri
unsigned long lastTelemetryTime = 0;

// Pengaturan jarak jauh dari aplikasi web (via MQTT commands)
bool alertsEnabled = true;
int hapticIntensity = 2;           // 1=Soft, 2=Medium, 3=Strong
float tremorThreshold = ALARM_TREMOR_THRESHOLD;
int stressThreshold = 80;

void setupWiFi() {
  delay(10);
  Serial.println("\n[WiFi] Menghubungkan ke Jaringan...");

  WiFi.mode(WIFI_STA);
  wifiManager.setConfigPortalTimeout(180);

  if (!wifiManager.autoConnect("NeuroFlow-AP")) {
    Serial.println("\n[WiFi] Gagal koneksi WiFi, restart perangkat...");
    delay(3000);
    ESP.restart();
    return;
  }

  Serial.println("\n[WiFi] Terhubung!");
  Serial.print("[WiFi] SSID: ");
  Serial.println(WiFi.SSID());
  Serial.print("[WiFi] IP   : ");
  Serial.println(WiFi.localIP());
}

void applyCommandSettings(const char* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];

  Serial.print("[MQTT Command] Diterima: ");
  Serial.println(msg);

  if (msg.indexOf("\"alerts_enabled\":false") >= 0 || msg.indexOf("\"alerts_enabled\": false") >= 0) {
    alertsEnabled = false;
  } else if (msg.indexOf("\"alerts_enabled\":true") >= 0 || msg.indexOf("\"alerts_enabled\": true") >= 0) {
    alertsEnabled = true;
  }

  int idx = msg.indexOf("\"haptic_intensity\":");
  if (idx >= 0) {
    int val = msg.substring(idx + 19, idx + 20).toInt();
    if (val >= 1 && val <= 3) hapticIntensity = val;
  }

  idx = msg.indexOf("\"tremor_threshold\":");
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
  if (String(topic) == mqtt_commands) {
    applyCommandSettings((const char*)payload, length);
  }
}

void reconnectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("[MQTT] Menghubungkan ke Broker... ");
    if (mqttClient.connect(client_id)) {
      Serial.println("TERHUBUNG!");
      mqttClient.subscribe(mqtt_commands);
      Serial.print("[MQTT] Subscribe: ");
      Serial.println(mqtt_commands);
    } else {
      Serial.print("Gagal, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" Mencoba kembali dalam 5 detik.");
      delay(5000);
    }
  }
}

void jalankanKalibrasi() {
  Serial.println("\n=== MEMULAI KALIBRASI MPU6050 ===");
  Serial.println("Pastikan perangkat dalam kondisi diam/tenang di permukaan datar...");
  
  float sumMag = 0;
  int sampleCount = 0;
  unsigned long startCalib = millis();
  
  while (millis() - startCalib < CALIBRATION_MS) {
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    
    // Hitung magnitudo total dari 3-axis akselerometer
    float mag = sqrt(a.acceleration.x * a.acceleration.x + 
                     a.acceleration.y * a.acceleration.y + 
                     a.acceleration.z * a.acceleration.z);
    sumMag += mag;
    sampleCount++;
    delay(20);
  }
  
  baseGravityMag = sumMag / sampleCount;
  Serial.print("[Kalibrasi Selesai] Base Gravity Offset Terhitung: ");
  Serial.print(baseGravityMag, 4);
  Serial.println(" m/s^2\n");
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  pinMode(HAPTIC_PIN, OUTPUT);
  digitalWrite(HAPTIC_PIN, LOW);

  // Inisialisasi Dua Jalur Bus I2C Fisik Sesuai Kode Testing Sukses Anda
  I2C_MPU.begin(17, 16, 100000); 
  I2C_MAX.begin(21, 22, 400000); 

  // Hubungkan MPU6050
  if (!mpu.begin(0x68, &I2C_MPU)) {
    Serial.println("[MPU6050] GAGAL! Periksa pin 17/16.");
    while (1) delay(10);
  }
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ); // Filter hardware internal membantu membuang high-frequency noise

  // Hubungkan MAX30102
  if (!maxSensor.begin(I2C_MAX, I2C_SPEED_FAST)) { 
    Serial.println("[MAX30102] GAGAL! Periksa pin 21/22.");
    while (1) delay(10);
  }

  // Konfigurasi Optimal untuk Deteksi Detak Jantung & Stres
  maxSensor.setup(60, 4, 2, 100, 411, 4096);
  maxSensor.setPulseAmplitudeRed(255); 
  maxSensor.setPulseAmplitudeGreen(0);  

  setupWiFi();
  mqttClient.setServer(mqtt_broker, mqtt_port);
  mqttClient.setCallback(mqttCallback);

  // Eksekusi Prosedur Kalibrasi Statis untuk Mengunci Nilai Gravitasi
  jalankanKalibrasi();
}

void loop() {
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  unsigned long currentTime = millis();
  static float tremorIntensity = 0;

  // 1. BLOK PROSESING SENSOR GERAK (SAMPLING 50Hz / 20ms)
  if (currentTime - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = currentTime;

    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);

    // Hitung magnitudo akselerasi saat ini
    float currentMag = sqrt(a.acceleration.x * a.acceleration.x + 
                            a.acceleration.y * a.acceleration.y + 
                            a.acceleration.z * a.acceleration.z);

    // Isolasi komponen getaran (AC) dengan mengurangi referensi statis hasil kalibrasi
    float acComponent = abs(currentMag - baseGravityMag);

    // Exponential Moving Average (EMA) Filter untuk mendapatkan visualisasi intensitas tremor yang halus
    tremorIntensity = (0.2 * acComponent) + (0.8 * tremorIntensity);
  }

  // 2. BLOK PROSESING DETAK JANTUNG (KONTINU / NON-BLOCKING)
  long irValue = maxSensor.getIR();
  
  // Algoritmik pengecekan puncak gelombang nadi (Plesthysmogram)
  if (checkForBeat(irValue) == true) {
    long delta = millis() - lastBeat;
    lastBeat = millis();

    beatsPerMinute = 60 / (delta / 1000.0);

    // Validasi rentang fisiologis detak jantung manusia normal
    if (beatsPerMinute < 200 && beatsPerMinute > 40) {
      beatAvg = (int)beatsPerMinute; 
    }
  }

  // 3. BLOK LOGIKA INTERVENSI HAPTIK (PRE-TREMOR & STRES ALERT)
  // Menghitung estimasi tingkat stres otonom berbasis respons detak jantung
  int calculatedStress = map(beatAvg, 60, 110, 15, 85);
  calculatedStress = constrain(calculatedStress, 0, 100);

  // Sesuaikan threshold berdasarkan intensitas haptic dari aplikasi
  float activeTremorThreshold = tremorThreshold;
  int activeStressThreshold = stressThreshold;
  if (hapticIntensity == 1) {
    activeTremorThreshold *= 1.25;
    activeStressThreshold = min(100, stressThreshold + 10);
  } else if (hapticIntensity == 3) {
    activeTremorThreshold *= 0.75;
    activeStressThreshold = max(50, stressThreshold - 10);
  }

  // Jika intensitas tremor melewati batas threshold atau indikasi stres melonjak tinggi
  if (alertsEnabled && (tremorIntensity > activeTremorThreshold || calculatedStress > activeStressThreshold)) {
    digitalWrite(HAPTIC_PIN, HIGH);
  } else {
    digitalWrite(HAPTIC_PIN, LOW);
  }

  // 4. BLOK TELEMETRI & PUBLISH MQTT (SETIAP 1 DETIK)
  if (currentTime - lastTelemetryTime >= TELEMETRY_INTERVAL) {
    lastTelemetryTime = currentTime;

    // Deteksi kehadiran jari pada sensor: Jika IR < 50000, berarti gelang tidak dipakai / tidak menyentuh kulit
    if (irValue < 50000) {
      beatAvg = 0;
      calculatedStress = 0;
    }

    // Mengonstruksi Alert Payload berformat JSON sesuai standar arsitektur NeuroFlow 
    String jsonPayload = "{";
    jsonPayload += "\"stress_level\":" + String(calculatedStress) + ",";
    jsonPayload += "\"heart_rate\":" + String(beatAvg) + ",";
    jsonPayload += "\"tremor_intensity\":" + String(tremorIntensity, 3) + ",";
    jsonPayload += "\"device_status\":\"ACTIVE\"";
    jsonPayload += "}";

    // Kirim data ke Cloud Backend via MQTT Broker [cite: 63]
    Serial.print("[MQTT Publish] Paket Terkirim: ");
    Serial.println(jsonPayload);
    mqttClient.publish(mqtt_topic, jsonPayload.c_str());
  }
}