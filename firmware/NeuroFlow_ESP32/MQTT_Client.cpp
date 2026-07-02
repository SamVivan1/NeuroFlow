#include "MQTT_Client.h"
#include <Arduino.h>

MQTT_Manager* MQTT_Manager::instance = nullptr;

MQTT_Manager::MQTT_Manager() : mqttClient(espClient), lastMqttConnectAttempt(0), cmdCallback(nullptr) {
    instance = this;
}

bool MQTT_Manager::setupWiFi() {
    delay(10);
    Serial.println("\n[WiFi] Menghubungkan ke " + String(WIFI_SSID) + "...");
    
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    int retries = 0;
    while (WiFi.status() != WL_CONNECTED && retries < 20) {
        delay(500);
        Serial.print(".");
        retries++;
    }

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("\n[WiFi] Gagal connect ke WiFi lokal, restart...");
        delay(3000);
        ESP.restart();
        return false;
    }
    Serial.println("\n[WiFi] Connected! IP: " + WiFi.localIP().toString());
    return true;
}

void MQTT_Manager::staticMqttCallback(char* topic, byte* payload, unsigned int length) {
    if (instance) instance->mqttCallback(topic, payload, length);
}

void MQTT_Manager::mqttCallback(char* topic, byte* payload, unsigned int length) {
    if (String(topic) == MQTT_TOPIC_COMMANDS) {
        String msg;
        for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
        if (cmdCallback) cmdCallback(msg);
    }
}

void MQTT_Manager::begin(CommandCallback cb) {
    cmdCallback = cb;
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setCallback(staticMqttCallback);
}

void MQTT_Manager::handle(unsigned long now) {
    if (!mqttClient.connected()) {
        if (now - lastMqttConnectAttempt >= MQTT_RETRY_INTERVAL_MS) {
            lastMqttConnectAttempt = now;
            if (mqttClient.connect(MQTT_CLIENT_ID)) {
                mqttClient.subscribe(MQTT_TOPIC_COMMANDS);
            }
        }
    } else {
        mqttClient.loop();
    }
}

bool MQTT_Manager::isConnected() {
    return mqttClient.connected();
}

void MQTT_Manager::publishTelemetry(const String& payload) {
    if (isConnected()) {
        mqttClient.publish(MQTT_TOPIC_DATA, payload.c_str());
    }
}

void MQTT_Manager::publishStatus(const char* status) {
    if (isConnected()) {
        String payload = String("{\"device_status\":\"") + status + "\"}";
        mqttClient.publish(MQTT_TOPIC_DATA, payload.c_str());
    }
}

void MQTT_Manager::disconnectForSleep() {
    if (isConnected()) {
        publishStatus("SLEEP");
        mqttClient.disconnect();
    }
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
}
