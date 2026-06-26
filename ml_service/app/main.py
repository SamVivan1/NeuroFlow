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
