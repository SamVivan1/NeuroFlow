import sys
import pandas as pd
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from ml_service.app.deep_learning_model import NeuroFlowMultimodalNet

def generate_synthetic_vitals(condition: str, acc_rms: float, is_stress_assumed: bool = False):
    """
    Generates synthetic vitals [HR, RMSSD, SDNN] based on clinical literature.
    """
    if "healthy" in condition.lower() or condition == "0":
        # Healthy: Normal HR, High HRV
        hr = np.random.normal(70, 5)
        rmssd = np.random.normal(60, 10)
        sdnn = np.random.normal(60, 10)
    else:
        # Parkinson's
        if is_stress_assumed or acc_rms > 0.05:
            # Stressed PD: Spiked HR, Severely Depressed HRV
            hr = np.random.normal(95, 10)
            rmssd = np.random.normal(15, 5)
            sdnn = np.random.normal(15, 5)
        else:
            # Baseline PD: Slightly elevated HR, Lower HRV than healthy
            hr = np.random.normal(75, 5)
            rmssd = np.random.normal(30, 5)
            sdnn = np.random.normal(30, 5)
            
    return np.array([hr, rmssd, sdnn], dtype=np.float32)

def main():
    print("NeuroFlow: Multimodal Deep Learning Training Pipeline (Dense Fusion)")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Target Device: {device}")
    
    csv_path = ROOT_DIR / "training" / "data" / "processed" / "pads_window_features_pd_vs_healthy.csv"
    print(f"Loading dataset from: {csv_path}")
    
    if not csv_path.exists():
        print(f"Error: {csv_path} not found!")
        return
        
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows.")
    
    # 75 MPU features
    drop_cols = ["subject_id", "condition", "label", "task_idx", "wrist_idx"]
    feature_cols = [c for c in df.columns if c not in drop_cols]
    
    X_mpu_raw = df[feature_cols].values
    
    # Scale MPU features
    scaler = StandardScaler()
    X_mpu_scaled = scaler.fit_transform(X_mpu_raw)
    
    y_raw = df["label"].values
    
    X_vitals = []
    y_multimodal = []
    
    for i in range(len(df)):
        condition = df.iloc[i]["condition"]
        acc_rms = df.iloc[i]["acc_mag_rms"]
        
        if "healthy" in str(condition).lower():
            label = 0
            vitals = generate_synthetic_vitals(condition, acc_rms, False)
        else:
            if acc_rms > 0.05: # High amplitude tremor -> Stress Amplified
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
    
    train_dataset = TensorDataset(
        torch.tensor(X_mpu_train, dtype=torch.float32), 
        torch.tensor(X_v_train, dtype=torch.float32), 
        torch.tensor(y_train, dtype=torch.long)
    )
    test_dataset = TensorDataset(
        torch.tensor(X_mpu_test, dtype=torch.float32), 
        torch.tensor(X_v_test, dtype=torch.float32), 
        torch.tensor(y_test, dtype=torch.long)
    )
    
    train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=128, shuffle=False)
    
    model = NeuroFlowMultimodalNet(mpu_features=len(feature_cols)).to(device)
    criterion = nn.NLLLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    epochs = 30
    print(f"Starting Training Loop for {epochs} Epochs...")
    
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        for mpu, vit, labels in train_loader:
            mpu, vit, labels = mpu.to(device), vit.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(mpu, vit)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
        train_acc = 100 * correct / total
        if epoch % 5 == 0 or epoch == epochs - 1:
            print(f"Epoch [{epoch+1}/{epochs}] Loss: {running_loss/len(train_loader):.4f} - Accuracy: {train_acc:.2f}%")
        
    print("Evaluating on Test Set...")
    model.eval()
    test_correct = 0
    test_total = 0
    with torch.no_grad():
        for mpu, vit, labels in test_loader:
            mpu, vit, labels = mpu.to(device), vit.to(device), labels.to(device)
            outputs = model(mpu, vit)
            _, predicted = torch.max(outputs.data, 1)
            test_total += labels.size(0)
            test_correct += (predicted == labels).sum().item()
            
    print(f"Final Test Accuracy: {100 * test_correct / test_total:.2f}%")
    
    model_dir = ROOT_DIR / "ml_service" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    save_path = model_dir / "neuroflow_multimodal.pt"
    
    torch.save(model.state_dict(), save_path)
    print(f"Model saved successfully to: {save_path}")
    
    # Save scaler for inference
    import joblib
    joblib.dump(scaler, model_dir / "mpu_scaler.joblib")
    print(f"Scaler saved to: {model_dir / 'mpu_scaler.joblib'}")

if __name__ == "__main__":
    main()
