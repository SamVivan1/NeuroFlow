import urllib.request
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATASET_URL = "https://raw.githubusercontent.com/realmichaelye/Stress-Prediction-Using-HRV/main/dataset/train.csv"
DATASET_PATH = os.path.join(DATA_DIR, "swell_hrv_train.csv")

print(f"Downloading dataset from {DATASET_URL}...")
try:
    urllib.request.urlretrieve(DATASET_URL, DATASET_PATH)
    print(f"Download successful. Saved to {DATASET_PATH}")
except Exception as e:
    print(f"Failed to download dataset: {e}")
