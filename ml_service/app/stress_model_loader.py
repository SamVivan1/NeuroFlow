import json
import joblib
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = BASE_DIR / "models"

class StressModelLoader:
    def __init__(self):
        config_files = sorted(MODEL_DIR.glob("neuroflow_stress_model_*_config.json"))
        
        if not config_files:
            raise FileNotFoundError("Config stress model tidak ditemukan. Jalankan train_stress_model.py")
            
        self.config_path = config_files[-1]
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
            
        self.model_path = MODEL_DIR / self.config["model_path"]
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file tidak ditemukan: {self.model_path}")
            
        self.model = joblib.load(self.model_path)
        self.feature_columns = self.config["feature_columns"]
        
    def predict_stress_probability(self, features: dict) -> float:
        # Build dataframe in exact order
        ordered_values = [
            float(features.get(col, 0.0))
            for col in self.feature_columns
        ]
        X = pd.DataFrame([ordered_values], columns=self.feature_columns)
        
        # Get probability of class 1 (Stressed)
        if hasattr(self.model, "predict_proba"):
            prob = self.model.predict_proba(X)[0, 1]
            return float(prob)
        return float(self.model.predict(X)[0])

try:
    stress_model = StressModelLoader()
except Exception as e:
    print(f"[StressModel] Warning: {e}")
    stress_model = None
