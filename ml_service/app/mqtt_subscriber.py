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
        stress_level = data.get("stress_level", 0.0)
        
        # New clinical pipeline: run tremor and stress context if samples exist
        if "samples" in data and isinstance(data["samples"], list):
            from app.raw_mpu_analyzer import analyze_tremor_stress_context
            from app.schemas import TremorStressContextRequest, RawMpuSample
            
            raw_samples = []
            for s in data["samples"]:
                raw_samples.append(RawMpuSample(**s))
                
            if len(raw_samples) >= 50:
                try:
                    req = TremorStressContextRequest(
                        activity=data.get("activity", "STATIONARY"),
                        heart_rate=data.get("heart_rate"),
                        avg_bpm_30s=data.get("avg_bpm_30s"),
                        rmssd=data.get("rmssd"),
                        sdnn=data.get("sdnn"),
                        pnn50=data.get("pnn50"),
                        sampling_rate_hz=data.get("sampling_rate_hz"),
                        samples=raw_samples
                    )
                    ctx = analyze_tremor_stress_context(req)
                    
                    tremor_intensity = ctx.get("tremor_intensity_score", 0)
                    stress_level = ctx.get("stress_context_score", 0)
                    
                    # Append clinical results back into payload for the UI
                    data["tremor_validity"] = ctx.get("tremor_validity")
                    data["tremor_intensity_label"] = ctx.get("tremor_intensity_label")
                    data["tremor_pattern_label"] = ctx.get("tremor_pattern_label")
                    data["dominant_frequency_hz"] = ctx.get("dominant_frequency_hz")
                    data["activity_artifact_score"] = ctx.get("activity_artifact_score")
                    data["stress_context_label"] = ctx.get("stress_context_label")
                    data["stress_interpretation"] = ctx.get("stress_interpretation")
                    data["motor_interpretation"] = ctx.get("motor_interpretation")
                    
                    # Also append the existing Parkinson motor model if requested
                    from app.raw_window_model_loader import raw_mpu_window_model
                    try:
                        prediction = raw_mpu_window_model.predict(raw_samples, sampling_rate_hz=50.0)
                        data["parkinson_model_class"] = prediction["predicted_class"]
                    except Exception:
                        pass
                        
                except Exception as ml_err:
                    print(f"[MQTT] Clinical Inference Error: {ml_err}")
        
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

