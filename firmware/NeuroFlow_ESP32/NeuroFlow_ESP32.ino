#include <Arduino.h>
#include <Wire.h>
#include "SystemConfig.h"
#include "MPU6050_Manager.h"
#include "MAX30102_Manager.h"
#include "Display.h"
#include "MQTT_Client.h"

// Hardware instances
TwoWire I2C_BUS = TwoWire(0);
MPU6050_Manager mpuManager;
MAX30102_Manager maxManager;
Display oledDisplay;
MQTT_Manager mqttManager;

// Timers and State
unsigned long lastSampleTime = 0;
unsigned long lastTelemetryTime = 0;
unsigned long lastActivityTime = 0;

bool alertsEnabled = true;
float tremorThreshold = DEFAULT_TREMOR_THRESHOLD;
int stressThreshold = 80;

// Utilities
float readBatteryVoltage() {
    int raw = analogRead(BATTERY_PIN);
    return (raw / (float)ADC_MAX_VALUE) * ADC_REFERENCE * VOLTAGE_DIVIDER_RATIO * BATTERY_CALIBRATION_FACTOR;
}

int batteryPercent(float voltage) {
    int percent = (int)round(((voltage - BATTERY_VOLTAGE_MIN) / (BATTERY_VOLTAGE_MAX - BATTERY_VOLTAGE_MIN)) * 100.0);
    return constrain(percent, 0, 100);
}

void goToDeepSleep() {
    Serial.println("\n[DEEP SLEEP] Mempersiapkan perangkat untuk tidur...");
    oledDisplay.sleep();
    mqttManager.disconnectForSleep();
    maxManager.shutDown();
    mpuManager.prepareForDeepSleep();
    
    esp_sleep_enable_ext0_wakeup((gpio_num_t)MPU_INT_PIN, 1);
    Serial.println("[DEEP SLEEP] Tidur sekarang. Gerakkan gelang untuk membangunkan.");
    delay(100);
    esp_deep_sleep_start();
}

void commandCallback(String msg) {
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

void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);

    esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
    if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT0) {
        Serial.println("\n[WAKEUP] Bangun karena ada pergerakan!");
    }

    pinMode(MPU_INT_PIN, INPUT_PULLDOWN);
    analogReadResolution(12);
    analogSetPinAttenuation(BATTERY_PIN, ADC_11db);

    I2C_BUS.begin(I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQ);

    if (!oledDisplay.begin(&I2C_BUS)) {
        Serial.println("[OLED] GAGAL!");
    }

    if (!mpuManager.begin(&I2C_BUS)) {
        Serial.println("[MPU6050] GAGAL!");
        oledDisplay.printLines("HARDWARE ERROR", "MPU6050 Disconnected", "Check I2C Pins", "SDA=21 SCL=22");
        while (1) delay(10);
    }

    if (!maxManager.begin(&I2C_BUS)) {
        Serial.println("[MAX30102] GAGAL!");
        oledDisplay.printLines("HARDWARE ERROR", "MAX30102 Disconnected", "Check I2C Connections", "");
        while (1) delay(10);
    }
    maxManager.wakeUp();

    oledDisplay.printLines("WiFi Status:", "Connecting...", "Check NeuroFlow-AP", "On Your Phone");
    if(mqttManager.setupWiFi()) {
        oledDisplay.printLines("WiFi Connected!", WiFi.SSID().c_str(), WiFi.localIP().toString().c_str(), "");
    }
    mqttManager.begin(commandCallback);

    Serial.println("\n=== MEMULAI KALIBRASI MPU6050 ===");
    oledDisplay.printLines("Kalibrasi MPU6050", "Harap Diam...", "Tunggu...", "5 Detik");
    mpuManager.calibrate();
    Serial.println("[Kalibrasi Selesai]");

    lastActivityTime = millis();
}

void loop() {
    unsigned long currentTime = millis();
    mqttManager.handle(currentTime);

    // 1. BLOK DETEKSI TREMOR & AKTIVITAS (50Hz)
    if (currentTime - lastSampleTime >= SAMPLE_INTERVAL_MS) {
        lastSampleTime = currentTime;
        float magnitude = mpuManager.getAccelMagnitude();
        mpuManager.update(magnitude);
    }

    // 2. BLOK VITALS (MAX30102 Polling Asinkron)
    maxManager.update(currentTime);

    if (maxManager.isFingerPresent() || mpuManager.getActivityLevel() != ACTIVITY_DIAM) {
        lastActivityTime = currentTime;
    }

    // 3. BLOK HISTORI DATA
    maxManager.updateHistory(currentTime);

    // 4. BLOK TELEMETRI & METRIK DISPLAY (Setiap 1 Detik)
    if (currentTime - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
        lastTelemetryTime = currentTime;

        int displayBPM = maxManager.getDisplayBPM(currentTime);
        int avgBPM = maxManager.getAverageBPM();
        if (displayBPM < 0) displayBPM = (avgBPM > 0) ? avgBPM : 0;

        int calculatedStress = map(displayBPM, 60, 110, 15, 85);
        calculatedStress = constrain(calculatedStress, 0, 100);

        float tremorIntensity = mpuManager.getTremorIntensity();
        float batteryVolt = readBatteryVoltage();
        int batteryPct = batteryPercent(batteryVolt);

        if (currentTime - lastActivityTime >= IDLE_TIMEOUT_MS) {
            Serial.println("\n[INFO] Perangkat idle terlalu lama.");
            goToDeepSleep();
        }

        const char* networkLabel = mqttManager.isConnected() ? "MQTT OK" : "MQTT DISC";

        if (mqttManager.isConnected()) {
            String jsonPayload = "{";
            jsonPayload += "\"activity\":\"" + String(mpuManager.getActivityLabel()) + "\",";
            jsonPayload += "\"stress_level\":" + String(calculatedStress) + ",";
            jsonPayload += "\"heart_rate\":" + String(displayBPM) + ",";
            jsonPayload += "\"avg_bpm_30s\":" + String(avgBPM) + ",";
            jsonPayload += "\"spo2\":" + String(maxManager.getDisplaySpO2(currentTime)) + ",";
            jsonPayload += "\"tremor_intensity\":" + String(tremorIntensity, 3) + ",";
            jsonPayload += "\"battery_pct\":" + String(batteryPct) + ",";
            jsonPayload += "\"device_status\":\"ACTIVE\"";
            jsonPayload += "}";
            mqttManager.publishTelemetry(jsonPayload);
        }

        int remain = maxManager.isWarmupDone() ? 0 : 
                     (WARMUP_MS > (currentTime - maxManager.getFingerDetectedTime())) ? 
                     ((WARMUP_MS - (currentTime - maxManager.getFingerDetectedTime())) / 1000) + 1 : 0;

        oledDisplay.showMainScreen(networkLabel, batteryVolt, batteryPct, displayBPM, 
                                   tremorIntensity, calculatedStress, 
                                   maxManager.isFingerPresent(), maxManager.isWarmupDone(), remain);
    }
}
