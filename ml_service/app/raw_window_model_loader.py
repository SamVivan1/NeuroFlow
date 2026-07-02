import json
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from app.schemas import RawMpuSample
from app.signal_features import extract_mpu_window_features


BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = BASE_DIR / "models"


class RawMpuWindowModel:
    def __init__(self):
        config_files = sorted(MODEL_DIR.glob("neuroflow_raw_mpu_window_*_config.json"))

        if not config_files:
            raise FileNotFoundError(
                "Config raw MPU window model tidak ditemukan. "
                "Jalankan dulu: python training/train_pads_window_model.py"
            )

        self.config_path = config_files[-1]

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.model_path = Path(self.config["model_path"])

        if not self.model_path.exists():
            fallback_path = MODEL_DIR / self.model_path.name

            if fallback_path.exists():
                self.model_path = fallback_path
            else:
                raise FileNotFoundError(f"Model file tidak ditemukan: {self.model_path}")

        self.model = joblib.load(self.model_path)
        self.model_name = self.config["model_name"]
        self.threshold = float(self.config["threshold"])
        self.feature_columns = self.config["feature_columns"]

    def infer_sampling_rate(self, samples: list[RawMpuSample], fallback: Optional[float]) -> float:
        if fallback is not None and fallback > 0:
            return float(fallback)

        timestamps = [
            float(sample.timestamp)
            for sample in samples
            if sample.timestamp is not None
        ]

        if len(timestamps) < 3:
            return float(self.config.get("sampling_rate_hz", 100.0))

        diffs = np.diff(np.asarray(timestamps, dtype=np.float64))
        diffs = diffs[diffs > 0]

        if diffs.size == 0:
            return float(self.config.get("sampling_rate_hz", 100.0))

        median_diff = float(np.median(diffs))

        if median_diff > 1.0:
            median_diff = median_diff / 1000.0

        if median_diff <= 0:
            return float(self.config.get("sampling_rate_hz", 100.0))

        return float(1.0 / median_diff)

    def get_score(self, X: pd.DataFrame) -> float:
        if hasattr(self.model, "decision_function"):
            return float(self.model.decision_function(X)[0])

        if hasattr(self.model, "predict_proba"):
            return float(self.model.predict_proba(X)[0, 1])

        return float(self.model.predict(X)[0])

    def predict(self, samples: list[RawMpuSample], sampling_rate_hz: Optional[float]):
        if len(samples) < 50:
            raise ValueError("Minimal butuh 50 sample. Disarankan 4 detik pada 50–100 Hz.")

        fs = self.infer_sampling_rate(samples, sampling_rate_hz)

        ax = np.asarray([s.ax for s in samples], dtype=np.float64)
        ay = np.asarray([s.ay for s in samples], dtype=np.float64)
        az = np.asarray([s.az for s in samples], dtype=np.float64)
        gx = np.asarray([s.gx for s in samples], dtype=np.float64)
        gy = np.asarray([s.gy for s in samples], dtype=np.float64)
        gz = np.asarray([s.gz for s in samples], dtype=np.float64)

        features = extract_mpu_window_features(
            ax=ax,
            ay=ay,
            az=az,
            gx=gx,
            gy=gy,
            gz=gz,
            sampling_rate_hz=fs,
        )

        ordered_values = [
            float(features.get(col, 0.0))
            for col in self.feature_columns
        ]

        X = pd.DataFrame(
            [ordered_values],
            columns=self.feature_columns,
        )

        score = self.get_score(X)

        predicted_label = int(score >= self.threshold)

        if predicted_label == 1:
            predicted_class = "Parkinson Motor Pattern"
            interpretation = (
                "Model raw MPU window mendeteksi pola motorik yang lebih mirip Parkinson-band. "
                "Threshold berasal dari hasil training model, bukan threshold manual sensor."
            )
        else:
            predicted_class = "Healthy / Non-Parkinson-like Pattern"
            interpretation = (
                "Model raw MPU window tidak mendeteksi pola motorik Parkinson-like pada window ini."
            )

        return {
            "model_name": self.model_name,
            "score": score,
            "threshold": self.threshold,
            "predicted_label": predicted_label,
            "predicted_class": predicted_class,
            "sampling_rate_hz": fs,
            "sample_count": len(samples),
            "window_duration_sec": len(samples) / fs,
            "dominant_frequency_hz": float(features.get("acc_mag_dom_freq", 0.0)),
            "energy_4_6_ratio": float(features.get("acc_mag_ratio_4_6_to_total", 0.0)),
            "energy_8_12_ratio": float(features.get("acc_mag_ratio_8_12_to_total", 0.0)),
            "interpretation": interpretation,
            "stress_status": "Not determined from MPU-only model",
            "stress_note": (
                "Model ini tidak memiliki label stress. Untuk membedakan stress tremor, "
                "gabungkan dengan heart rate/HRV dari MAX30102 atau model stress terpisah."
            ),
        }


raw_mpu_window_model = RawMpuWindowModel()
