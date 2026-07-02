import os
import json
import asyncio
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

from app.raw_mpu_analyzer import analyze_tremor_stress_context
from app.raw_window_model_loader import raw_mpu_window_model
from app.schemas import RawMpuWindowRequest, RawMpuWindowModelResponse, TremorStressContextRequest, TremorStressContextResponse
from app.model_loader import motor_model
from app.schemas import FeaturePredictionRequest, FeaturePredictionResponse

from app.database import engine, Base
from app.mqtt_subscriber import start_mqtt, register_callback

# Create DB tables
Base.metadata.create_all(bind=engine)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

from fastapi.middleware.cors import CORSMiddleware

manager = ConnectionManager()

main_loop = None

# Bridge MQTT to WebSockets
def mqtt_to_ws_bridge(data: dict):
    if main_loop is not None and not main_loop.is_closed():
        asyncio.run_coroutine_threadsafe(manager.broadcast(data), main_loop)

register_callback(mqtt_to_ws_bridge)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    # Startup
    start_mqtt()
    yield
    # Shutdown

app = FastAPI(
    title="NeuroFlow ML Service",
    description="ML inference service and WebSocket gateway for NeuroFlow.",
    version="0.2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, wait for client messages if any
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "model_name": motor_model.model_name,
        "feature_count": len(motor_model.feature_columns),
        "threshold": motor_model.threshold,
    }

@app.post("/predict/features", response_model=FeaturePredictionResponse)
def predict_from_features(payload: FeaturePredictionRequest):
    try:
        result = motor_model.predict(payload.features)
        return {
            "subject_id": payload.subject_id,
            **result,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Inference gagal: {exc}",
        ) from exc

@app.get("/predict/demo")
def demo_prediction():
    feature_csv = Path(
        os.getenv(
            "PADS_FEATURE_CSV",
            Path(__file__).resolve().parents[2]
            / "training"
            / "data"
            / "processed"
            / "pads_motion_features_pd_vs_healthy.csv",
        )
    )

    if not feature_csv.exists():
        raise HTTPException(status_code=404, detail="Feature CSV tidak ditemukan.")

    df = pd.read_csv(feature_csv)
    sample = df.sample(1, random_state=7).iloc[0]

    features = {
        col: float(sample[col])
        for col in motor_model.feature_columns
    }

    result = motor_model.predict(features)

    return {
        "subject_id": str(sample["subject_id"]),
        "condition": str(sample["condition"]),
        "true_label": int(sample["label"]),
        **result,
        "demo_note": "Demo ini memakai sample dari dataset PADS lokal.",
    }

@app.post("/predict/raw-mpu-model", response_model=RawMpuWindowModelResponse)
def predict_raw_mpu_model(payload: RawMpuWindowRequest):
    try:
        return raw_mpu_window_model.predict(
            samples=payload.samples,
            sampling_rate_hz=payload.sampling_rate_hz,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Raw MPU model inference gagal: {exc}",
        ) from exc


@app.post("/predict/tremor-stress-context", response_model=TremorStressContextResponse)
def predict_tremor_stress_context(payload: TremorStressContextRequest):
    try:
        # 1. Run the strict heuristic and artifact gating
        result_dict = analyze_tremor_stress_context(payload)
        
        # 2. If valid, run the ML model for Parkinson motor pattern detection
        model_result = None
        if len(payload.samples) >= 50:
            try:
                model_result = raw_mpu_window_model.predict(
                    samples=payload.samples,
                    sampling_rate_hz=payload.sampling_rate_hz,
                )
            except Exception:
                pass # Model fallback
                
        result_dict["motor_model_result"] = model_result
        return TremorStressContextResponse(**result_dict)
        
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Tremor-Stress Context inference failed: {exc}",
        ) from exc

