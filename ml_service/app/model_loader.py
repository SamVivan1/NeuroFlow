import json
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

MODEL_PATH = BASE_DIR / "models" / "neuroflow_pads_pd_vs_healthy_svm_rbf_cv.joblib"
CONFIG_PATH = BASE_DIR / "models" / "neuroflow_pads_pd_vs_healthy_svm_rbf_cv_config.json"


class NeuroFlowMotorModel:
    def __init__(self):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model file tidak ditemukan: {MODEL_PATH}")

        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"Config file tidak ditemukan: {CONFIG_PATH}")

        self.model = joblib.load(MODEL_PATH)

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.model_name = self.config["model_name"]
        self.threshold = float(self.config["threshold"])
        self.feature_columns: List[str] = self.config["feature_columns"]

    def build_feature_frame(self, features: Dict[str, float]) -> Tuple[pd.DataFrame, int, int]:
        """
        Menyusun fitur request ke urutan yang sama dengan training.
        Missing feature diisi 0.0 agar API tidak crash, tetapi jumlahnya tetap dilaporkan.
        """

        missing_features = [
            col for col in self.feature_columns
            if col not in features
        ]

        extra_features = [
            col for col in features.keys()
            if col not in self.feature_columns
        ]

        ordered_values = [
            float(features.get(col, 0.0))
            for col in self.feature_columns
        ]

        X = pd.DataFrame(
            [ordered_values],
            columns=self.feature_columns,
        )

        return X, len(missing_features), len(extra_features)

    def get_score(self, X: pd.DataFrame) -> float:
        """
        SVM RBF memakai decision_function.
        Score ini bukan probabilitas, melainkan margin keputusan.
        """

        if hasattr(self.model, "decision_function"):
            score = self.model.decision_function(X)[0]
            return float(score)

        if hasattr(self.model, "predict_proba"):
            score = self.model.predict_proba(X)[0, 1]
            return float(score)

        score = self.model.predict(X)[0]
        return float(score)

    def predict(self, features: Dict[str, float]):
        X, missing_count, extra_count = self.build_feature_frame(features)

        score = self.get_score(X)

        predicted_label = int(score >= self.threshold)

        if predicted_label == 1:
            predicted_class = "Parkinson Motor Pattern"
            interpretation = (
                "Pola sinyal motorik lebih mirip kelompok Parkinson pada dataset PADS. "
                "Ini bukan diagnosis final dan belum menyimpulkan stress tremor."
            )
        else:
            predicted_class = "Healthy / Non-Parkinson-like Pattern"
            interpretation = (
                "Pola sinyal motorik lebih mirip kelompok healthy pada dataset PADS. "
                "Ini bukan diagnosis final."
            )

        return {
            "model_name": self.model_name,
            "score": score,
            "threshold": self.threshold,
            "predicted_label": predicted_label,
            "predicted_class": predicted_class,
            "interpretation": interpretation,
            "missing_feature_count": missing_count,
            "extra_feature_count": extra_count,
        }


motor_model = NeuroFlowMotorModel()
