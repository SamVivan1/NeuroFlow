import urllib.request
import zipfile
import os
import shutil

LIBRARIES_DIR = r"C:\Arduino\libraries"
os.makedirs(LIBRARIES_DIR, exist_ok=True)

URLS = {
    "Adafruit_GFX": "https://github.com/adafruit/Adafruit-GFX-Library/archive/refs/heads/master.zip",
    "Adafruit_SSD1306": "https://github.com/adafruit/Adafruit_SSD1306/archive/refs/heads/master.zip"
}

for name, url in URLS.items():
    zip_path = os.path.join(LIBRARIES_DIR, f"{name}.zip")
    print(f"Downloading {name}...")
    urllib.request.urlretrieve(url, zip_path)
    
    print(f"Extracting {name}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(LIBRARIES_DIR)
        
    os.remove(zip_path)

print("Library Display berhasil ditambahkan!")
