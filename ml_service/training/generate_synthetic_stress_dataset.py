import pandas as pd
import numpy as np
import os

# Create a highly realistic synthetic dataset modeled after the SWELL-KW / WESAD HRV distributions
# 0 = No Stress (Relaxed), 1 = Stressed

N_SAMPLES = 5000

np.random.seed(42)

# Generate labels: 60% Relaxed, 40% Stressed
labels = np.random.choice([0, 1], size=N_SAMPLES, p=[0.6, 0.4])

data = []
for label in labels:
    if label == 0: # Relaxed
        hr = np.random.normal(loc=65.0, scale=8.0)
        rmssd = np.random.normal(loc=45.0, scale=15.0)  # Higher RMSSD when relaxed
        pnn50 = np.random.normal(loc=25.0, scale=10.0)
        sdnn = np.random.normal(loc=60.0, scale=15.0)
        spo2 = np.random.normal(loc=98.5, scale=1.0)
    else: # Stressed
        hr = np.random.normal(loc=88.0, scale=12.0)
        rmssd = np.random.normal(loc=18.0, scale=8.0)   # Lower RMSSD when stressed
        pnn50 = np.random.normal(loc=5.0, scale=4.0)
        sdnn = np.random.normal(loc=30.0, scale=10.0)
        spo2 = np.random.normal(loc=97.0, scale=1.5)
        
    # Clip to realistic physiological bounds
    hr = max(40, min(140, hr))
    rmssd = max(5, min(150, rmssd))
    pnn50 = max(0, min(80, pnn50))
    sdnn = max(10, min(200, sdnn))
    spo2 = max(90, min(100, spo2))
    
    data.append([hr, rmssd, pnn50, sdnn, spo2, label])
    
df = pd.DataFrame(data, columns=["hr", "rmssd", "pnn50", "sdnn", "spo2", "stress_label"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
out_path = os.path.join(DATA_DIR, "synthetic_stress_hrv.csv")

df.to_csv(out_path, index=False)
print(f"Successfully generated {N_SAMPLES} realistic clinical HRV rows at {out_path}")
