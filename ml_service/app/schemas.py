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

class TremorStressContextRequest(BaseModel):
    activity: Optional[str] = "STATIONARY"
    heart_rate: Optional[float] = None
    avg_bpm_30s: Optional[float] = None
    rmssd: Optional[float] = None
    sdnn: Optional[float] = None
    pnn50: Optional[float] = None
    sampling_rate_hz: Optional[float] = None
    samples: List[RawMpuSample]

class TremorStressContextResponse(BaseModel):
    sample_count: int
    sampling_rate_hz: float
    window_duration_sec: float
    activity: str
    dominant_frequency_hz: float
    acc_rms: float
    gyro_rms: float
    jerk_rms: float
    ratio_3_8_to_total: float
    ratio_4_6_to_total: float
    ratio_8_12_to_total: float
    spectral_concentration: float
    activity_artifact_score: float
    tremor_validity: str
    tremor_intensity_score: int
    tremor_intensity_label: str
    tremor_pattern_label: str
    motor_interpretation: str
    stress_context_score: int
    stress_context_label: str
    stress_interpretation: str
    warning: str
    motor_model_result: Optional[RawMpuWindowModelResponse] = None
