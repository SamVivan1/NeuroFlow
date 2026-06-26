import time
import json
import random
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "neuroflow/device/data"

def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[Dummy Telemetry] Connected to MQTT broker with result code {reason_code}")

client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

print("[Dummy Telemetry] Starting random telemetry stream...")
print("Press Ctrl+C to stop.")

import math

try:
    while True:
        heart_rate = random.randint(60, 110)
        
        # Simulate HRV parameters based on heart rate to test the Stress ML model
        # Higher HR -> Stressed -> Lower HRV
        if heart_rate > 80:
            rmssd = random.randint(10, 25)
            sdnn = random.randint(20, 40)
            pnn50 = random.randint(1, 10)
            is_tremor = True
            # Tremor amplitude scales with stress (higher HR = more violent tremor)
            tremor_amplitude = ((heart_rate - 80) / 30.0) * 1.5 + 0.5
        else:
            rmssd = random.randint(35, 60)
            sdnn = random.randint(50, 80)
            pnn50 = random.randint(15, 35)
            is_tremor = False
            tremor_amplitude = 0
            
        # Simulate 1 second of 50Hz raw MPU data
        # If is_tremor, simulate Parkinson-like resting tremor (4-6 Hz sine wave)
        samples = []
        for i in range(50):
            t = i / 50.0
            if is_tremor:
                # 5 Hz dominant frequency for Parkinsonian tremor
                # Inject tremor on the Z-axis (gravity) so the vector magnitude oscillates at 5Hz natively!
                ax = random.uniform(-0.1, 0.1)
                ay = random.uniform(-0.1, 0.1)
                az = 1.0 + (math.sin(2 * math.pi * 5 * t) * tremor_amplitude) + random.uniform(-0.05, 0.05)
            else:
                ax = random.uniform(-0.1, 0.1)
                ay = random.uniform(-0.1, 0.1)
                az = 1.0 + random.uniform(-0.05, 0.05)
                
            samples.append({
                "timestamp": time.time() + t,
                "ax": ax, "ay": ay, "az": az,
                "gx": random.uniform(-0.5, 0.5), "gy": random.uniform(-0.5, 0.5), "gz": random.uniform(-0.5, 0.5)
            })
            
        payload = {
            "activity": random.choice(["STATIONARY", "WALKING", "STATIONARY", "STATIONARY"]),
            "heart_rate": heart_rate,
            "rmssd": rmssd,
            "sdnn": sdnn,
            "pnn50": pnn50,
            "avg_bpm_30s": heart_rate - random.randint(-3, 3),
            "spo2": random.randint(95, 100),
            "battery_pct": random.randint(15, 100),
            "device_status": "ACTIVE",
            "samples": samples
        }
        
        json_payload = json.dumps(payload)
        client.publish(MQTT_TOPIC, json_payload)
        print(f"Published window of 50 samples with HR={heart_rate} and RMSSD={rmssd}")
        
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[Dummy Telemetry] Stopping...")
    client.loop_stop()
    client.disconnect()
