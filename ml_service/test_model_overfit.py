import sys
import pandas as pd
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report
import joblib

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from ml_service.app.deep_learning_model import NeuroFlowMultimodalNet

def generate_synthetic_vitals(condition: str, acc_rms: float, is_stress_assumed: bool = False):
    if "healthy" in condition.lower() or condition == "0":
        hr = np.random.normal(70, 5)
        rmssd = np.random.normal(60, 10)
        sdnn = np.random.normal(60, 10)
    else:
        if is_stress_assumed or acc_rms > 0.05:
            hr = np.random.normal(95, 10)
            rmssd = np.random.normal(15, 5)
            sdnn = np.random.normal(15, 5)
        else:
            hr = np.random.normal(75, 5)
            rmssd = np.random.normal(30, 5)
            sdnn = np.random.normal(30, 5)
    return np.array([hr, rmssd, sdnn], dtype=np.float32)

def main():
    print("=== NeuroFlow Model Overfitting Analysis ===")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    csv_path = ROOT_DIR / "training" / "data" / "processed" / "pads_window_features_pd_vs_healthy.csv"
    df = pd.read_csv(csv_path)
    
    drop_cols = ["subject_id", "condition", "label", "task_idx", "wrist_idx"]
    feature_cols = [c for c in df.columns if c not in drop_cols]
    
    X_mpu_raw = df[feature_cols].values
    y_raw = df["label"].values
    
    scaler_path = ROOT_DIR / "ml_service" / "models" / "mpu_scaler.joblib"
    scaler = joblib.load(scaler_path)
    X_mpu_scaled = scaler.transform(X_mpu_raw)
    
    X_vitals = []
    y_multimodal = []
    for i in range(len(df)):
        condition = df.iloc[i]["condition"]
        acc_rms = df.iloc[i]["acc_mag_rms"]
        if "healthy" in str(condition).lower():
            label = 0
            vitals = generate_synthetic_vitals(condition, acc_rms, False)
        else:
            if acc_rms > 0.05:
                label = 2
                vitals = generate_synthetic_vitals(condition, acc_rms, True)
            else:
                label = 1
                vitals = generate_synthetic_vitals(condition, acc_rms, False)
        X_vitals.append(vitals)
        y_multimodal.append(label)
        
    X_vitals = np.array(X_vitals)
    y_multimodal = np.array(y_multimodal)
    
    X_mpu_train, X_mpu_test, X_v_train, X_v_test, y_train, y_test = train_test_split(
        X_mpu_scaled, X_vitals, y_multimodal, test_size=0.2, random_state=42, stratify=y_multimodal
    )
    
    model_path = ROOT_DIR / "ml_service" / "models" / "neuroflow_multimodal.pt"
    model = NeuroFlowMultimodalNet(mpu_features=len(feature_cols)).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()

    def evaluate(mpu_data, vitals_data, labels):
        mpu_t = torch.tensor(mpu_data, dtype=torch.float32).to(device)
        vit_t = torch.tensor(vitals_data, dtype=torch.float32).to(device)
        labels_t = torch.tensor(labels, dtype=torch.long).to(device)
        
        with torch.no_grad():
            outputs = model(mpu_t, vit_t)
            _, predicted = torch.max(outputs, 1)
            
        acc = (predicted == labels_t).sum().item() / len(labels)
        return acc, predicted.cpu().numpy()

    # 1. Baseline Accuracy
    base_acc, base_preds = evaluate(X_mpu_test, X_v_test, y_test)
    print(f"\n1. Baseline Test Accuracy (Both MPU & Vitals): {base_acc*100:.2f}%")
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, base_preds))
    
    # 2. Vitals Permutation Test (Shuffle Vitals to break correlation)
    np.random.seed(42)
    X_v_shuffled = np.random.permutation(X_v_test)
    shuf_vit_acc, _ = evaluate(X_mpu_test, X_v_shuffled, y_test)
    print(f"\n2. Accuracy with SHUFFLED Vitals (Testing MPU reliance): {shuf_vit_acc*100:.2f}%")
    
    # 3. MPU Permutation Test (Shuffle MPU to break correlation)
    X_mpu_shuffled = np.random.permutation(X_mpu_test)
    shuf_mpu_acc, _ = evaluate(X_mpu_shuffled, X_v_test, y_test)
    print(f"3. Accuracy with SHUFFLED MPU (Testing Vitals reliance): {shuf_mpu_acc*100:.2f}%")
    
    print("\n=== CONCLUSION ===")
    if shuf_vit_acc < 0.50 and shuf_mpu_acc > 0.90:
        print("WARNING: OVERFITTING DETECTED! The model is ignoring the MPU motor data and is solely relying on the synthetic Vitals data. It has memorized the synthetic rules.")
    elif shuf_mpu_acc < 0.50 and shuf_vit_acc > 0.90:
        print("Model is relying mostly on MPU motor data and ignoring Vitals.")
    else:
        print("Model is using a healthy mix of both MPU and Vitals for its decisions.")

if __name__ == "__main__":
    main()
