import urllib.request
import zipfile
import os
import shutil

LIBRARIES_DIR = r"C:\Arduino\libraries"
os.makedirs(LIBRARIES_DIR, exist_ok=True)

URLS = {
    "Adafruit_MPU6050": "https://github.com/adafruit/Adafruit_MPU6050/archive/refs/heads/master.zip",
    "Adafruit_BusIO": "https://github.com/adafruit/Adafruit_BusIO/archive/refs/heads/master.zip",
    "Adafruit_Sensor": "https://github.com/adafruit/Adafruit_Sensor/archive/refs/heads/master.zip",
    "SparkFun_MAX3010x": "https://github.com/sparkfun/SparkFun_MAX3010x_Sensor_Library/archive/refs/heads/master.zip",
    "PubSubClient": "https://github.com/knolleary/pubsubclient/archive/refs/heads/master.zip"
}

for name, url in URLS.items():
    zip_path = os.path.join(LIBRARIES_DIR, f"{name}.zip")
    print(f"Downloading {name}...")
    urllib.request.urlretrieve(url, zip_path)
    
    print(f"Extracting {name}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(LIBRARIES_DIR)
        
    os.remove(zip_path)

print("Semua library berhasil di-download dan di-extract ke C:\\Arduino\\libraries!")
