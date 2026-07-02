import torch
import torch.nn as nn
import torch.nn.functional as F

class NeuroFlowMultimodalNet(nn.Module):
    """
    Multimodal Deep Learning Architecture for Parkinson's Stress-Amplified Tremor.
    
    Branch 1 (MPU6050): Deep Dense Layers to process (B, 75) frequency/statistical features.
    Branch 2 (MAX30102): Dense layers to process (B, 3) HR/HRV vitals.
    Fusion: Late concatenation + classification into 3 classes.
    """
    def __init__(self, mpu_features=75, vital_features=3, num_classes=3):
        super(NeuroFlowMultimodalNet, self).__init__()
        
        # --- Branch 1: MPU6050 (Dense) ---
        # Input shape: (Batch, 75)
        self.mpu_fc1 = nn.Linear(mpu_features, 128)
        self.mpu_bn1 = nn.BatchNorm1d(128)
        self.mpu_fc2 = nn.Linear(128, 64)
        self.mpu_bn2 = nn.BatchNorm1d(64)
        self.mpu_fc3 = nn.Linear(64, 64)
        
        # --- Branch 2: Vitals (Dense) ---
        # Input shape: (Batch, 3) -> HR, RMSSD, SDNN
        self.vitals_fc1 = nn.Linear(vital_features, 16)
        self.vitals_fc2 = nn.Linear(16, 16)
        
        # --- Fusion Layer ---
        # Combine MPU output (64) + Vitals output (16) = 80
        self.fusion_fc1 = nn.Linear(64 + 16, 32)
        self.dropout = nn.Dropout(0.3)
        self.fusion_fc2 = nn.Linear(32, num_classes)
        
    def forward(self, mpu_x, vitals_x):
        # MPU Branch
        x1 = F.relu(self.mpu_bn1(self.mpu_fc1(mpu_x)))
        x1 = F.relu(self.mpu_bn2(self.mpu_fc2(x1)))
        mpu_feat = F.relu(self.mpu_fc3(x1)) # (B, 64)
        
        # Vitals Branch
        v_feat = F.relu(self.vitals_fc1(vitals_x))
        v_feat = F.relu(self.vitals_fc2(v_feat)) # (B, 16)
        
        # Fusion
        fused = torch.cat((mpu_feat, v_feat), dim=1) # (B, 80)
        
        out = F.relu(self.fusion_fc1(fused))
        out = self.dropout(out)
        out = self.fusion_fc2(out) # (B, 3)
        
        # Use log_softmax for training with NLLLoss, or raw logits for CrossEntropyLoss
        return F.log_softmax(out, dim=1)

class DLModelRunner:
    def __init__(self, model_path: str):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = NeuroFlowMultimodalNet().to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()
        
    def predict(self, mpu_tensor, vitals_tensor):
        """
        mpu_tensor: numpy array of shape (75,)
        vitals_tensor: numpy array of shape (3,) -> [HR, RMSSD, SDNN]
        """
        import numpy as np
        
        mpu_x = torch.tensor(mpu_tensor, dtype=torch.float32).unsqueeze(0).to(self.device)
        v_x = torch.tensor(vitals_tensor, dtype=torch.float32).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            log_probs = self.model(mpu_x, v_x)
            probs = torch.exp(log_probs)
            pred_class = torch.argmax(probs, dim=1).item()
            
        return pred_class, probs.squeeze().cpu().numpy()
