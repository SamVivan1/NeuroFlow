import os
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException

from app.model_loader import motor_model
from app.schemas import FeaturePredictionRequest, FeaturePredictionResponse


app = FastAPI(
    title="NeuroFlow ML Service",
    description=(
        "ML inference service untuk baseline Parkinson motor-pattern detector. "
        "Model ini memakai fitur IMU hasil ekstraksi dari dataset PADS."
    ),
    version="0.1.0",
)


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
    """
    Endpoint khusus development/demo.
    Mengambil satu sample dari feature CSV lokal, lalu menjalankan inference.

    Catatan:
    Ini bukan endpoint produksi dan bukan telemetry real-time.
    """
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
        raise HTTPException(
            status_code=404,
            detail=(
                f"Feature CSV tidak ditemukan: {feature_csv}. "
                "Copy file pads_motion_features_pd_vs_healthy.csv ke training/data/processed/ "
                "atau set environment variable PADS_FEATURE_CSV."
            ),
        )

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
        "demo_note": (
            "Demo ini memakai sample dari dataset PADS lokal. "
            "Belum merepresentasikan telemetry real-time NeuroFlow."
        ),
    }
