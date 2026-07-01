#ifndef SYSTEM_CONFIG_H
#define SYSTEM_CONFIG_H

// ==================== CONFIGURATION ====================

#define WIFI_SSID "CutAdek"
#define WIFI_PASSWORD "harilibur"


// but we set constants for defaults here.
#define MQTT_BROKER "broker.hivemq.com"
#define MQTT_PORT 1883
#define MQTT_TOPIC_DATA "neuroflow/device/data"
#define MQTT_TOPIC_COMMANDS "neuroflow/device/commands"
#define MQTT_CLIENT_ID "neuroflow_esp32_wristband"

// Timings
#define CALIBRATION_MS 5000
#define SAMPLE_INTERVAL_MS 20      // 50Hz for MPU6050
#define TELEMETRY_INTERVAL_MS 1000 // Send data every 1s
#define MQTT_RETRY_INTERVAL_MS 5000
#define IDLE_TIMEOUT_MS 300000     // 5 minutes for deep sleep

// I2C Pins
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22
#define I2C_FREQ 400000

// Activity & Tremor Constants
#define ACTIVITY_WINDOW_SIZE 50
#define STD_THRESHOLD_JALAN 0.35f
#define STD_THRESHOLD_LARI 0.85f
#define DEFAULT_TREMOR_THRESHOLD 0.40f

// MAX30102 Constants
#define IR_FINGER_THRESHOLD 30000
#define DC_ALPHA 0.85f
#define PEAK_MIN_INTERVAL_MS 400
#define PEAK_MAX_INTERVAL_MS 1500
#define PEAK_THRESHOLD 300
#define WARMUP_MS 8000
#define LAST_DATA_HOLD_MS 2000
#define HISTORY_SIZE 30

// Battery & Pin Config
#define BATTERY_PIN 34
#define MPU_INT_PIN 33
#define BATTERY_VOLTAGE_MIN 3.3f
#define BATTERY_VOLTAGE_MAX 4.2f
#define VOLTAGE_DIVIDER_RATIO 2.0f
#define ADC_MAX_VALUE 4095
#define ADC_REFERENCE 3.3f
#define BATTERY_CALIBRATION_FACTOR 1.133f

// OLED Config
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

#endif // SYSTEM_CONFIG_H
