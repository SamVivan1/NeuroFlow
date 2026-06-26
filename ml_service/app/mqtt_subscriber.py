import json
import threading
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from app.database import SessionLocal
from app.db_models import TelemetryRecord

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "neuroflow/device/data"

# Callbacks for WebSocket broadcast
on_message_callbacks = []

def register_callback(cb):
    on_message_callbacks.append(cb)

def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[MQTT] Connected with result code {reason_code}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    try:
        data = json.loads(payload)
        
        tremor_intensity = data.get("tremor_intensity", 0.0)
        
        # If the device sends a window of raw MPU samples, run cloud ML inference!
        if "samples" in data and isinstance(data["samples"], list):
            from app.raw_window_model_loader import raw_mpu_window_model
            from app.schemas import RawMpuSample
            
            raw_samples = []
            for s in data["samples"]:
                raw_samples.append(RawMpuSample(**s))
                
            if len(raw_samples) >= 50:
                try:
                    prediction = raw_mpu_window_model.predict(raw_samples, sampling_rate_hz=50.0)
                    # Use the energy ratio in Parkinson band (4-6Hz) as the tremor intensity, scaled to 100
                    tremor_intensity = min(100.0, max(0.0, prediction["energy_4_6_ratio"] * 100.0))
                except Exception as ml_err:
                    print(f"[MQTT] ML Inference Error: {ml_err}")
        
        # Save to DB
        
        # 2. Extract physiological features and infer stress using the new Secondary ML Model!
        stress_level = data.get("stress_level", 0)
        
        # If the device sends HRV features, we run true Stress Inference
        if "rmssd" in data:
            from app.stress_model_loader import stress_model
            if stress_model is not None:
                try:
                    stress_features = {
                        "hr": data.get("heart_rate", 60),
                        "rmssd": data.get("rmssd", 40),
                        "pnn50": data.get("pnn50", 20),
                        "sdnn": data.get("sdnn", 50),
                        "spo2": data.get("spo2", 98)
                    }
                    stress_prob = stress_model.predict_stress_probability(stress_features)
                    # Convert 0.0-1.0 probability to 0-100 percentage
                    stress_level = int(stress_prob * 100)
                except Exception as stress_err:
                    print(f"[MQTT] Stress Inference Error: {stress_err}")
        
        db = SessionLocal()
        record = TelemetryRecord(
            activity=data.get("activity", "UNKNOWN"),
            stress_level=stress_level,
            heart_rate=data.get("heart_rate", 0),
            avg_bpm_30s=data.get("avg_bpm_30s", 0),
            spo2=data.get("spo2", 0),
            tremor_intensity=tremor_intensity,
            battery_pct=data.get("battery_pct", 0),
            device_status=data.get("device_status", "UNKNOWN")
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        db.close()
        
        # Add the computed tremor and stress back to the payload before broadcasting
        data["tremor_intensity"] = tremor_intensity
        data["stress_level"] = stress_level
        
        # Broadcast to websockets
        for cb in on_message_callbacks:
            cb(data)
            
    except Exception as e:
        print(f"[MQTT] Error parsing message: {e}")

def start_mqtt():
    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    thread = threading.Thread(target=client.loop_forever, daemon=True)
    thread.start()
    print("[MQTT] Subscriber thread started.")

