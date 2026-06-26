import json
from pathlib import Path

import pandas as pd
import requests


FEATURE_CSV = Path("training/data/processed/pads_motion_features_pd_vs_healthy.csv")
CONFIG_PATH = Path("ml_service/models/neuroflow_pads_pd_vs_healthy_svm_rbf_cv_config.json")
API_URL = "http://127.0.0.1:8001/predict/features"


def main():
    df = pd.read_csv(FEATURE_CSV)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    feature_columns = config["feature_columns"]

    sample = df.sample(1, random_state=7).iloc[0]

    features = {
        col: float(sample[col])
        for col in feature_columns
    }

    payload = {
        "subject_id": str(sample["subject_id"]),
        "features": features,
    }

    response = requests.post(API_URL, json=payload, timeout=30)
    response.raise_for_status()

    print("\n=== TRUE DATA ===")
    print("Subject ID:", sample["subject_id"])
    print("Condition :", sample["condition"])
    print("True Label:", sample["label"])

    print("\n=== API RESPONSE ===")
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
