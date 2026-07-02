import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


MODEL_PATH = Path("training/models/neuroflow_pads_pd_vs_healthy_svm_rbf_cv.joblib")
CONFIG_PATH = Path("training/models/neuroflow_pads_pd_vs_healthy_svm_rbf_cv_config.json")
FEATURE_CSV = Path("training/data/processed/pads_motion_features_pd_vs_healthy.csv")


def get_model_score(model, X):
    """
    Untuk SVM, skor diambil dari decision_function.
    Semakin tinggi skor, semakin condong ke kelas Parkinson.
    """

    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]

    if hasattr(model, "decision_function"):
        return model.decision_function(X)

    return model.predict(X)


def classify_score(score: float, threshold: float):
    """
    Rule utama:
    score >= threshold berarti Parkinson motor pattern terdeteksi.
    """

    if score >= threshold:
        return "Parkinson Motor Pattern"

    return "Healthy / Non-Parkinson-like Pattern"


def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model tidak ditemukan: {MODEL_PATH}")

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config tidak ditemukan: {CONFIG_PATH}")

    if not FEATURE_CSV.exists():
        raise FileNotFoundError(f"Feature CSV tidak ditemukan: {FEATURE_CSV}")

    model = joblib.load(MODEL_PATH)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    threshold = float(config["threshold"])
    feature_columns = config["feature_columns"]

    df = pd.read_csv(FEATURE_CSV)

    sample = df.sample(1, random_state=7).iloc[0]

    X = pd.DataFrame([sample[feature_columns]])

    score = float(get_model_score(model, X)[0])

    prediction = classify_score(score, threshold)

    print("\n=== SAMPLE INFERENCE ===")
    print("Subject ID :", sample["subject_id"])
    print("Condition  :", sample["condition"])
    print("True Label :", sample["label"])
    print("Score      :", score)
    print("Threshold  :", threshold)
    print("Prediction :", prediction)


if __name__ == "__main__":
    main()
