import paho.mqtt.client as mqtt
import time
import json
import random

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC_DATA = "neuroflow/device/data"

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")

client = mqtt.Client(client_id="neuroflow_demo_simulator")
client.on_connect = on_connect
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

print("=== NEUROFLOW DEMO SIMULATOR ===")
print("Memancarkan data palsu ke Dashboard untuk keperluan Sidang/Demo.")
print("Skenario: Stress-Amplified Parkinson Tremor")
print("Tekan CTRL+C untuk berhenti.\n")

try:
    while True:
        # Simulasi Tremor Parkinson yang konsisten (Amplitudo sedang, Frekuensi 5Hz konstan)
        # Tremor score di kisaran 70-85
        tremor_val = random.uniform(70.0, 85.0)
        
        # Simulasi HR yang tinggi karena Stres (BPM 95 - 110)
        hr_val = int(random.uniform(95, 110))
        
        # Stress level tinggi
        stress_val = int(random.uniform(80, 95))
        
        payload = {
            "activity": "STATIONARY",
            "stress_level": stress_val,
            "heart_rate": hr_val,
            "avg_bpm_30s": hr_val - 2,
            "spo2": 98,
            "tremor_intensity": round(tremor_val, 1),
            "battery_pct": 100,
            "device_status": "ACTIVE"
        }
        
        json_str = json.dumps(payload)
        client.publish(MQTT_TOPIC_DATA, json_str)
        print(f"Mengirim: Tremor={payload['tremor_intensity']}% | HR={payload['heart_rate']} BPM | Stress={payload['stress_level']}%")
        
        time.sleep(1) # Kirim setiap detik seperti ESP32

except KeyboardInterrupt:
    print("\nSimulasi dihentikan.")
    client.loop_stop()
    client.disconnect()
