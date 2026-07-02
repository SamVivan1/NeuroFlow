import requests
import numpy as np
import time
import math

API_URL = "http://127.0.0.1:8000/predict/tremor-stress-context"

def build_synthetic_window(freq_hz: float, amp_g: float, fs: float = 100.0, duration_sec: float = 4.0, walk_amp: float = 0.0, typing_noise: bool = False):
    t = np.linspace(0, duration_sec, int(fs * duration_sec), endpoint=False)
    
    # Base gravity on Z
    az = np.ones_like(t)
    ax = np.zeros_like(t)
    ay = np.zeros_like(t)
    gx = np.zeros_like(t)
    gy = np.zeros_like(t)
    gz = np.zeros_like(t)
    
    if amp_g > 0:
        tremor = amp_g * np.sin(2 * np.pi * freq_hz * t)
        ax += tremor
        ay += tremor
        az += tremor
        gx += tremor * 2.0
        gy += tremor * 1.5
        gz += tremor * 1.0

    if walk_amp > 0:
        walk = walk_amp * np.sin(2 * np.pi * 1.8 * t)
        ax += walk
        ay += walk
        az += walk
        gx += walk
    
    if typing_noise:
        # High jerk spikes
        spike_indices = np.random.choice(len(t), size=int(len(t)*0.1), replace=False)
        ax[spike_indices] += np.random.normal(0, 0.5, size=len(spike_indices))
        ay[spike_indices] += np.random.normal(0, 0.5, size=len(spike_indices))

    samples = []
    base_time = int(time.time() * 1000)
    for i in range(len(t)):
        samples.append({
            "timestamp": base_time + int(i * (1000/fs)),
            "ax": float(ax[i]),
            "ay": float(ay[i]),
            "az": float(az[i]),
            "gx": float(gx[i]),
            "gy": float(gy[i]),
            "gz": float(gz[i])
        })
    return samples

def run_test(name: str, payload: dict):
    print(f"\n--- Running Test: {name} ---")
    try:
        resp = requests.post(API_URL, json=payload, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Artifact Score: {data['activity_artifact_score']:.2f}")
            print(f"Tremor Validity: {data['tremor_validity']}")
            print(f"Tremor Label: {data['tremor_intensity_label']}")
            print(f"Tremor Pattern: {data['tremor_pattern_label']}")
            print(f"Stress Label: {data['stress_context_label']}")
            print(f"Interpretation: {data['motor_interpretation']}")
        else:
            print(f"Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    print("Testing the Tremor-Stress Context API...")

    # 1. Synthetic 5 Hz stationary tremor
    run_test("1. 5Hz Stationary Tremor (Parkinson-like)", {
        "activity": "STATIONARY",
        "heart_rate": 70,
        "rmssd": 45,
        "sampling_rate_hz": 100,
        "samples": build_synthetic_window(5.0, 0.1)
    })

    # 2. Synthetic no tremor
    run_test("2. No Tremor (Rest Calm)", {
        "activity": "STATIONARY",
        "heart_rate": 65,
        "rmssd": 50,
        "sampling_rate_hz": 100,
        "samples": build_synthetic_window(0.0, 0.0)
    })

    # 3. Synthetic typing artifact
    run_test("3. Typing Artifact", {
        "activity": "TYPING",
        "heart_rate": 75,
        "rmssd": 40,
        "sampling_rate_hz": 100,
        "samples": build_synthetic_window(0.0, 0.0, typing_noise=True)
    })

    # 4. Synthetic walking
    run_test("4. Walking Artifact", {
        "activity": "WALKING",
        "heart_rate": 90,
        "rmssd": 35,
        "sampling_rate_hz": 100,
        "samples": build_synthetic_window(0.0, 0.0, walk_amp=0.3)
    })

    # 5. Synthetic high HR + low HRV + valid 5 Hz tremor
    run_test("5. Stress-Amplified Tremor", {
        "activity": "STATIONARY",
        "heart_rate": 105,
        "rmssd": 18,
        "sampling_rate_hz": 100,
        "samples": build_synthetic_window(5.0, 0.2)
    })

    # 6. High HR + low HRV without tremor
    run_test("6. Pure Physiological Stress (No Tremor)", {
        "activity": "STATIONARY",
        "heart_rate": 95,
        "rmssd": 22,
        "sampling_rate_hz": 100,
        "samples": build_synthetic_window(0.0, 0.0)
    })
