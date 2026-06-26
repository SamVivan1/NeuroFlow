from typing import Dict, Optional

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
