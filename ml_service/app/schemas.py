from typing import Dict, Optional, List

from pydantic import BaseModel, Field


class FeaturePredictionRequest(BaseModel):
    subject_id: Optional[str] = Field(
        default=None,
        description="ID subject/patient opsional untuk tracking request.",
    )

    features: Dict[str, float] = Field(
        ...,
        description="Dictionary fitur sesuai feature_columns pada config model.",
    )


class FeaturePredictionResponse(BaseModel):
    subject_id: Optional[str]
    model_name: str
    score: float
    threshold: float
    predicted_label: int
    predicted_class: str
    interpretation: str
    missing_feature_count: int
    extra_feature_count: int


class RawMpuSample(BaseModel):
    timestamp: Optional[float] = Field(default=None)
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float


class RawMpuWindowRequest(BaseModel):
    samples: List[RawMpuSample]
    sampling_rate_hz: Optional[float] = None


class RawMpuWindowModelResponse(BaseModel):
    model_name: str
    score: float
    threshold: float
    predicted_label: int
    predicted_class: str
    sampling_rate_hz: float
    sample_count: int
    window_duration_sec: float
    dominant_frequency_hz: float
    energy_4_6_ratio: float
    energy_8_12_ratio: float
    interpretation: str
    stress_status: str
    stress_note: str
