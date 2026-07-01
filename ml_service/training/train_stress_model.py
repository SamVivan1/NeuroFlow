import os
import json
import joblib
import pandas as pd
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "synthetic_stress_hrv.csv")
MODEL_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

def train_model():
    print(f"Loading dataset from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    
    feature_columns = ["hr", "rmssd", "pnn50", "sdnn", "spo2"]
    X = df[feature_columns]
    y = df["stress_label"]
    
    print("Splitting dataset into train/test (80/20)...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print("Training RandomForestClassifier...")
    model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_train, y_train)
    
    print("Evaluating model...")
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"Accuracy: {acc:.4f}")
    print(classification_report(y_test, y_pred))
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_name = f"neuroflow_stress_model_{timestamp}.pkl"
    config_name = f"neuroflow_stress_model_{timestamp}_config.json"
    
    model_path = os.path.join(MODEL_DIR, model_name)
    config_path = os.path.join(MODEL_DIR, config_name)
    
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")
    
    config = {
        "model_name": "NeuroFlow Stress RandomForest v1",
        "model_path": model_name,
        "feature_columns": feature_columns,
        "threshold": 0.5,
        "classes": {0: "Relaxed", 1: "Stressed"},
        "accuracy": acc,
        "trained_on": timestamp
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"Config saved to {config_path}")

if __name__ == "__main__":
    train_model()
