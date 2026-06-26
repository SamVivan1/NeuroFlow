import json
import math

import requests


API_URL = "http://127.0.0.1:8001/predict/raw-mpu-model"

FS = 100
DURATION_SEC = 4
FREQ_HZ = 5.0


def main():
    samples = []

    for i in range(FS * DURATION_SEC):
        t = i / FS

        tremor = 0.12 * math.sin(2 * math.pi * FREQ_HZ * t)

        samples.append(
            {
                "timestamp": int(t * 1000),
                "ax": tremor,
                "ay": 0.02 * math.sin(2 * math.pi * FREQ_HZ * t),
                "az": 1.0,
                "gx": 0.4 * math.sin(2 * math.pi * FREQ_HZ * t),
                "gy": 0.1 * math.sin(2 * math.pi * FREQ_HZ * t),
                "gz": 0.0,
            }
        )

    payload = {
        "sampling_rate_hz": FS,
        "samples": samples,
    }

    response = requests.post(API_URL, json=payload, timeout=30)

    print("Status:", response.status_code)
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
