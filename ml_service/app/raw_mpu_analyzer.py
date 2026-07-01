import math
from typing import Optional, Dict, Any

import numpy as np

from app.schemas import RawMpuSample, TremorStressContextRequest
from app.deep_learning_model import DLModelRunner
import joblib
from pathlib import Path

DL_MODEL = None
SCALER = None

ROOT = Path(__file__).resolve().parents[2]
model_path = ROOT / "models" / "neuroflow_multimodal.pt"
scaler_path = ROOT / "models" / "mpu_scaler.joblib"


def infer_sampling_rate(samples: list[RawMpuSample], fallback: Optional[float]) -> float:
    if fallback is not None and fallback > 0:
        return float(fallback)
    timestamps = [float(s.timestamp) for s in samples if s.timestamp is not None]
    if len(timestamps) < 3:
        return 50.0
    diffs = np.diff(np.asarray(timestamps, dtype=np.float64))
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        return 50.0
    median_diff = float(np.median(diffs))
    if median_diff > 1.0:
        median_diff = median_diff / 1000.0
    if median_diff <= 0:
        return 50.0
    return float(1.0 / median_diff)


def detrend(signal: np.ndarray) -> np.ndarray:
    return signal - np.mean(signal)


def calculate_jerk(signal: np.ndarray, fs: float) -> np.ndarray:
    return np.diff(signal) * fs


def get_spectrum(signal: np.ndarray, fs: float):
    signal = detrend(signal.astype(np.float64))
    if signal.size < 8:
        return np.array([]), np.array([])
    spectrum = np.fft.rfft(signal)
    power = np.abs(spectrum) ** 2
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / fs)
    return freqs, power


def band_energy(freqs: np.ndarray, power: np.ndarray, low: float, high: float) -> float:
    if freqs.size == 0:
        return 0.0
    mask = (freqs >= low) & (freqs <= high)
    return float(np.sum(power[mask]))


def analyze_tremor_stress_context(request: TremorStressContextRequest) -> Dict[str, Any]:
    samples = request.samples
    if len(samples) < 50:
        return {
            "error": "Insufficient sensor window for stable tremor analysis.",
            "sample_count": len(samples),
            "warning": "This is not a clinical diagnosis."
        }

    fs = infer_sampling_rate(samples, request.sampling_rate_hz)
    duration_sec = len(samples) / fs

    ax = np.asarray([s.ax for s in samples], dtype=np.float64)
    ay = np.asarray([s.ay for s in samples], dtype=np.float64)
    az = np.asarray([s.az for s in samples], dtype=np.float64)
    gx = np.asarray([s.gx for s in samples], dtype=np.float64)
    gy = np.asarray([s.gy for s in samples], dtype=np.float64)
    gz = np.asarray([s.gz for s in samples], dtype=np.float64)

    acc_mag = np.sqrt(ax**2 + ay**2 + az**2)
    gyro_mag = np.sqrt(gx**2 + gy**2 + gz**2)
    # Load DL Model if not loaded
    if DL_MODEL is None or SCALER is None:
        try:
            DL_MODEL = DLModelRunner(str(model_path))
            SCALER = joblib.load(str(scaler_path))
        except Exception as e:
            print(f"Error loading DL model: {e}")
            return {"error": f"Failed to load Deep Learning model: {e}"}
            
    # Extract 75 features required by the Dense model
    from app.signal_features import extract_mpu_window_features
    features_dict = extract_mpu_window_features(ax, ay, az, gx, gy, gz, fs)
    
    # Exclude non-numerical meta columns if any are generated
    drop_keys = ["subject_id", "condition", "label", "task_idx", "wrist_idx"]
    feature_vector = []
    
    # We must ensure the order matches the CSV exactly!
    # The CSV columns were extracted using extract_mpu_window_features. 
    # We just iterate over the dictionary values in order, skipping drops.
    for k, v in features_dict.items():
        if k not in drop_keys:
            feature_vector.append(float(v))
            
    mpu_tensor = np.array(feature_vector, dtype=np.float32).reshape(1, -1)
    
    # Scale MPU features
    mpu_scaled = SCALER.transform(mpu_tensor)[0] # Shape (75,)
    
    # Prepare Vitals Tensor
    hr = float(request.heart_rate or 0)
    rmssd = float(request.rmssd or 0)
    sdnn = float(request.sdnn or 0)
    vitals_tensor = np.array([hr, rmssd, sdnn], dtype=np.float32)
    
    # Run Inference
    try:
        pred_class, probs = DL_MODEL.predict(mpu_scaled, vitals_tensor)
    except Exception as e:
        print(f"DL Inference Error: {e}")
        return {"error": "DL Inference failed."}
        
    # Interpret DL Output
    # Classes: 0 = Normal, 1 = Parkinson Tremor, 2 = Stress-Amplified Tremor
    class_labels = ["Normal / No Tremor", "Parkinson Motor Pattern", "Stress-Amplified Parkinson Tremor"]
    pred_label = class_labels[pred_class]
    
    confidence = float(np.max(probs) * 100)
    
    # We still need to return some visual stats for the frontend dashboard
    # The frontend expects tremor_intensity_score (0-100) and stress_context_score (0-100)
    
    if pred_class == 0:
        tremor_score = 10
        stress_score = 10
        stress_label = "Normal state"
    elif pred_class == 1:
        tremor_score = 60
        stress_score = 20
        stress_label = "Baseline tremor (no strong stress context)"
    else: # pred_class == 2
        tremor_score = 90
        stress_score = 90
        stress_label = "Stress-amplified tremor"
        
    return {
        "sample_count": len(samples),
        "sampling_rate_hz": fs,
        "window_duration_sec": duration_sec,
        "activity": activity,
        "dl_prediction": pred_label,
        "dl_confidence": confidence,
        "tremor_validity": "valid",
        "tremor_intensity_score": tremor_score,
        "tremor_intensity_label": "Severe Tremor" if pred_class == 2 else ("Moderate Tremor" if pred_class == 1 else "Normal"),
        "tremor_pattern_label": pred_label,
        "motor_interpretation": f"Deep Learning classified window as {pred_label} with {confidence:.1f}% confidence.",
        "stress_context_score": stress_score,
        "stress_context_label": stress_label,
        "stress_interpretation": f"Multimodal AI detected: {stress_label}",
        "warning": "Driven by PyTorch Multimodal DL model."
    }
