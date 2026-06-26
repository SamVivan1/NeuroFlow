import time
import math
import random
from app.raw_window_model_loader import raw_mpu_window_model
from app.schemas import RawMpuSample

samples = []
heart_rate = 94
tremor_amplitude = ((heart_rate - 80) / 30.0) * 1.5 + 0.5
for i in range(50):
    t = i / 50.0
    ax = (math.sin(2 * math.pi * 5 * t) * tremor_amplitude) + random.uniform(-0.1, 0.1)
    ay = (math.sin(2 * math.pi * 5 * t) * tremor_amplitude) + random.uniform(-0.1, 0.1)
    az = 1.0 + random.uniform(-0.1, 0.1)
    samples.append(RawMpuSample(
        timestamp=time.time() + t,
        ax=ax, ay=ay, az=az,
        gx=random.uniform(-0.5, 0.5), gy=random.uniform(-0.5, 0.5), gz=random.uniform(-0.5, 0.5)
    ))

try:
    prediction = raw_mpu_window_model.predict(samples, sampling_rate_hz=50.0)
    print("Prediction:", prediction["energy_4_6_ratio"])
except Exception as e:
    print("Error:", e)
