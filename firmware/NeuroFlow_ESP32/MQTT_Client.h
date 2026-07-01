#ifndef MQTT_CLIENT_H
#define MQTT_CLIENT_H

#include <WiFi.h>
#include <PubSubClient.h>
#include "SystemConfig.h"

// Define a callback type for incoming commands
typedef void (*CommandCallback)(String msg);

class MQTT_Manager {
private:
    WiFiClient espClient;
    PubSubClient mqttClient;
    
    unsigned long lastMqttConnectAttempt;
    CommandCallback cmdCallback;

    static MQTT_Manager* instance;
    static void staticMqttCallback(char* topic, byte* payload, unsigned int length);
    void mqttCallback(char* topic, byte* payload, unsigned int length);

public:
    MQTT_Manager();
    
    bool setupWiFi();
    void begin(CommandCallback cb);
    void handle(unsigned long now);
    
    bool isConnected();
    void publishTelemetry(const String& payload);
    void publishStatus(const char* status);
    void disconnectForSleep();
};

#endif // MQTT_CLIENT_H
