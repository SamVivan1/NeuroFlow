# NeuroFlow

## Panduan Run Cepat

Bagian ini berisi urutan paling cepat untuk menjalankan NeuroFlow dari firmware ESP32, frontend dashboard, sampai backend ML service.

---

## 1. Clone Branch

```bash
git clone -b feature/ml-service-pads-baseline-v2 https://github.com/SamVivan1/NeuroFlow.git
cd NeuroFlow
```

Pastikan branch aktif:

```bash
git branch --show-current
```

Output yang benar:

```text
feature/ml-service-pads-baseline-v2
```

---

## 2. Setup Firmware ESP32 di Arduino IDE

### 2.1 Install Arduino IDE

Gunakan Arduino IDE versi terbaru yang tersedia di sistem masing-masing.

Setelah Arduino IDE terbuka, masuk ke:

```text
File → Preferences
```

Pada bagian **Additional Boards Manager URLs**, tambahkan URL ESP32 board package:

```text
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

Lalu buka:

```text
Tools → Board → Boards Manager
```

Cari:

```text
esp32
```

Install board package:

```text
esp32 by Espressif Systems
```

---

### 2.2 Pilih Board ESP32

Masuk ke:

```text
Tools → Board
```

Pilih board sesuai perangkat. Umumnya:

```text
ESP32 Dev Module
```

Pilih port:

```text
Tools → Port
```

Pilih port ESP32 yang terdeteksi, misalnya:

```text
/dev/ttyUSB0
/dev/ttyACM0
COM3
COM4
```

Di Linux, jika port tidak bisa diakses, jalankan:

```bash
sudo usermod -aG dialout $USER
```

Kemudian logout dan login ulang.

---

### 2.3 Install Library Arduino

Buka:

```text
Tools → Manage Libraries
```

Install library berikut jika digunakan oleh sketch firmware:

```text
PubSubClient
ArduinoJson
Adafruit MPU6050
Adafruit Unified Sensor
Wire
```

Untuk MAX30102, library yang umum digunakan adalah salah satu dari berikut, tergantung sketch yang dipakai:

```text
SparkFun MAX3010x Pulse and Proximity Sensor Library
MAX30105 library
```

Catatan: sesuaikan library dengan `#include` yang ada di file `.ino`.

---

### 2.4 Buka Firmware

Firmware tersedia di folder:

```text
firmware/
```

Beberapa file firmware yang tersedia:

```text
firmware/esp32 v0.1.ino
firmware/esp32 v1.ino
firmware/esp32/esp32.ino
firmware/testing/testing.ino
firmware/NeuroFlow_ESP32/
```

Gunakan firmware utama yang sesuai dengan struktur terbaru project. Jika memakai folder Arduino project, buka file `.ino` dari folder tersebut melalui Arduino IDE.

---

### 2.5 Konfigurasi Wi-Fi dan MQTT

Di dalam firmware, sesuaikan konfigurasi berikut:

```cpp
const char* ssid = "NAMA_WIFI";
const char* password = "PASSWORD_WIFI";

const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;

const char* data_topic = "neuroflow/device/data";
const char* command_topic = "neuroflow/device/commands";
```

Pastikan topic MQTT firmware sama dengan konfigurasi frontend:

```env
MQTT_TOPIC_DATA=neuroflow/device/data
MQTT_TOPIC_COMMANDS=neuroflow/device/commands
```

---

### 2.6 Upload Firmware

Klik tombol:

```text
Verify
```

Jika tidak ada error, klik:

```text
Upload
```

Buka Serial Monitor:

```text
Tools → Serial Monitor
```

Gunakan baud rate sesuai firmware, biasanya:

```text
115200
```

Jika berhasil, ESP32 harus menampilkan status koneksi Wi-Fi, MQTT, dan pembacaan sensor.

---

## 3. Jalankan ML Service

Masuk ke folder ML service:

```bash
cd ml_service
```

Buat virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependency:

```bash
pip install fastapi uvicorn numpy pandas scikit-learn joblib pydantic requests
```

Jalankan backend ML:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Test service:

```bash
curl http://127.0.0.1:8001/health
```

Output yang benar:

```json
{
  "status": "ok"
}
```

---

## 4. Jalankan Frontend

Buka terminal baru dari root project:

```bash
cd frontend
npm install
npm run dev
```

Frontend berjalan di:

```text
http://localhost:3000
```

Buat file environment lokal jika diperlukan:

```bash
nano .env.local
```

Isi:

```env
ML_SERVICE_URL=http://127.0.0.1:8001
MQTT_BROKER=broker.hivemq.com
MQTT_PORT=1883
MQTT_TOPIC_DATA=neuroflow/device/data
MQTT_TOPIC_COMMANDS=neuroflow/device/commands
```

Jangan commit file `.env.local`.

---

## 5. Test Telemetry MQTT

Setelah ESP32 menyala dan frontend berjalan, test stream telemetry:

```bash
curl http://localhost:3000/api/telemetry
```

Output harus berbentuk Server-Sent Events seperti ini:

```text
data: {"stress_level":0,"heart_rate":78,"tremor_intensity":12,"device_status":"connected","received_at":1780000000000,"ax":0.01,"ay":-0.02,"az":1,"gx":0.2,"gy":0.1,"gz":-0.1}
```

Field penting untuk raw MPU6050:

```text
ax, ay, az, gx, gy, gz
```

Jika field tersebut muncul, berarti raw data sensor sudah masuk ke frontend.

---

## 6. Test Endpoint Raw MPU Model

Pastikan ML service berjalan di port `8001`.

Dari root project:

```bash
python training/test_raw_mpu_model_endpoint.py
```

Output yang diharapkan:

```json
{
  "model_name": "svm_rbf",
  "score": 0.123,
  "threshold": -0.195,
  "predicted_label": 1,
  "predicted_class": "Parkinson Motor Pattern",
  "sampling_rate_hz": 100.0,
  "sample_count": 400,
  "window_duration_sec": 4.0,
  "dominant_frequency_hz": 5.0,
  "energy_4_6_ratio": 0.8,
  "energy_8_12_ratio": 0.0,
  "stress_status": "Not determined from MPU-only model"
}
```

Aturan keputusan model:

```text
score >= threshold → Parkinson Motor Pattern
score < threshold  → Healthy / Non-Parkinson-like Pattern
```

Threshold berasal dari hasil training model, bukan threshold manual dari frontend.

---

## 7. Test Proxy Frontend ke ML Service

Pastikan dua service aktif:

```text
Frontend Next.js → http://localhost:3000
ML FastAPI       → http://127.0.0.1:8001
```

Test route proxy:

```bash
curl -X POST http://localhost:3000/api/ml/raw-mpu-model \
  -H "Content-Type: application/json" \
  -d '{"sampling_rate_hz":100,"samples":[]}'
```

Jika route aktif, response akan berupa error validasi karena sample kosong. Itu normal.

Untuk inference valid, kirim minimal 50 sample raw MPU. Untuk hasil lebih stabil, gunakan window sekitar 4 detik pada 100 Hz atau sekitar 400 sample.

---

# Deskripsi Project

NeuroFlow adalah sistem monitoring berbasis IoT dan machine learning untuk membantu observasi pola motorik pada pasien Parkinson serta konteks stres fisiologis. Sistem ini terdiri dari perangkat ESP32, sensor MPU6050, sensor MAX30102, dashboard web berbasis Next.js, dan backend ML service berbasis FastAPI.

Project ini tidak ditujukan sebagai alat diagnosis medis final. Output model digunakan sebagai informasi monitoring dan analisis awal, bukan pengganti penilaian dokter.

---

# Fitur Utama

* Monitoring telemetry dari ESP32.
* Komunikasi MQTT antara device dan dashboard.
* Dashboard Next.js untuk menampilkan heart rate, intensitas tremor, status device, breathing guide, reports, dan settings.
* Backend FastAPI untuk inference machine learning.
* Dukungan raw MPU6050:

  * `ax`
  * `ay`
  * `az`
  * `gx`
  * `gy`
  * `gz`
* Model baseline Parkinson motor-pattern berbasis dataset PADS.
* Threshold inference berasal dari hasil training model.
* Struktur awal untuk pengembangan stress-context model berbasis MAX30102.

---

# Arsitektur Sistem

```text
ESP32 + MPU6050 + MAX30102
        |
        | MQTT
        v
Frontend MQTT Bridge
        |
        v
Next.js Dashboard
        |
        | API Proxy
        v
FastAPI ML Service
        |
        v
Model Inference
```

Alur raw MPU:

```text
ax, ay, az, gx, gy, gz
        |
        v
Window Buffer
        |
        v
Feature Extraction
        |
        v
Trained ML Model
        |
        v
score >= trained_threshold
        |
        v
Parkinson Motor Pattern / Non-Parkinson-like Pattern
```

Alur stress-context yang direncanakan:

```text
MAX30102 heart rate / HRV
        |
        v
Stress-context model
        |
        v
Stress-likely / Non-stress-likely context
```

---

# Struktur Repository

```text
NeuroFlow/
├── firmware/
│   └── Firmware ESP32 dan sketch testing
│
├── frontend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── commands/
│   │   │   ├── telemetry/
│   │   │   └── ml/
│   │   ├── breathe/
│   │   ├── reports/
│   │   ├── settings/
│   │   └── page.tsx
│   ├── components/
│   ├── context/
│   └── lib/
│
├── ml_service/
│   ├── app/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── model_loader.py
│   │   ├── raw_window_model_loader.py
│   │   ├── raw_mpu_analyzer.py
│   │   └── signal_features.py
│   └── models/
│
├── training/
│   ├── train_pads_motion_features.py
│   ├── train_pads_motion_cv_threshold.py
│   ├── train_pads_window_model.py
│   └── test_raw_mpu_model_endpoint.py
│
├── stitch/
├── docker-compose.yml
└── DOCKER_DEPLOYMENT.md
```

---

# Frontend

Frontend menggunakan Next.js dan berfungsi sebagai dashboard utama NeuroFlow.

Route utama:

```text
/           → Dashboard utama
/breathe    → Panduan breathing
/reports    → Laporan
/settings   → Pengaturan perangkat
```

API route frontend:

```text
GET  /api/telemetry
POST /api/commands
POST /api/ml/motor-pattern
GET  /api/ml/motor-pattern/demo
POST /api/ml/raw-mpu-model
```

File penting:

```text
frontend/context/TelemetryProvider.tsx
frontend/lib/mqtt-bridge.ts
frontend/lib/telemetry-utils.ts
frontend/lib/types.ts
frontend/app/api/telemetry/route.ts
frontend/app/api/ml/raw-mpu-model/route.ts
```

---

# ML Service

ML service menggunakan FastAPI.

Endpoint utama:

```text
GET  /health
POST /predict/features
GET  /predict/demo
POST /predict/raw-mpu-model
```

File penting:

```text
ml_service/app/main.py
ml_service/app/schemas.py
ml_service/app/model_loader.py
ml_service/app/raw_window_model_loader.py
ml_service/app/signal_features.py
ml_service/app/raw_mpu_analyzer.py
```

---

# Model dan Threshold

Model raw MPU menggunakan pendekatan:

```text
raw MPU window
→ ekstraksi fitur sinyal
→ model machine learning
→ score
→ threshold hasil training
→ prediksi
```

Output model:

```text
Parkinson Motor Pattern
Healthy / Non-Parkinson-like Pattern
```

Contoh config model:

```json
{
  "model_name": "svm_rbf",
  "threshold": -0.195,
  "decision_rule": "score >= threshold => Parkinson Motor Pattern"
}
```

Threshold ini berasal dari proses training dan validasi model. Threshold ini bukan angka manual dari UI.

---

# Training Model Raw MPU

Dataset yang digunakan untuk baseline adalah PADS. Dataset ini digunakan untuk membuat model motor-pattern Parkinson vs healthy/non-Parkinson-like.

Struktur dataset yang dibutuhkan:

```text
training/data/pads/
├── preprocessed/
│   └── movement/
│       ├── 001_ml.bin
│       ├── 002_ml.bin
│       └── ...
└── patients/
    ├── patient_001.json
    ├── patient_002.json
    └── ...
```

Run training:

```bash
python training/train_pads_window_model.py \
  --base-dir /path/to/pads
```

Contoh:

```bash
python training/train_pads_window_model.py \
  --base-dir ~/Projects/MachineLearning/Parkinsson/training/data/pads
```

Output training:

```text
training/data/processed/pads_window_features_pd_vs_healthy.csv
training/reports/pads_window_model/raw_mpu_window_model_report.json
ml_service/models/neuroflow_raw_mpu_window_<model>.joblib
ml_service/models/neuroflow_raw_mpu_window_<model>_config.json
```

File `.joblib` tidak disarankan untuk langsung di-commit kecuali menggunakan Git LFS.

---

# Format Payload MQTT

Payload dapat dikirim dalam bentuk langsung:

```json
{
  "stress_level": 0,
  "heart_rate": 78,
  "tremor_intensity": 12,
  "device_status": "connected",
  "ax": 0.01,
  "ay": -0.02,
  "az": 1.0,
  "gx": 0.2,
  "gy": 0.1,
  "gz": -0.1
}
```

Atau bentuk nested:

```json
{
  "heart_rate": 78,
  "stress_level": 0,
  "tremor_intensity": 12,
  "device_status": "connected",
  "mpu": {
    "accelX": 0.01,
    "accelY": -0.02,
    "accelZ": 1.0,
    "gyroX": 0.2,
    "gyroY": 0.1,
    "gyroZ": -0.1
  }
}
```

Frontend akan menormalisasi payload tersebut menjadi:

```ts
{
  stress_level: number;
  heart_rate: number;
  tremor_intensity: number;
  device_status: string;
  received_at: number;
  ax?: number;
  ay?: number;
  az?: number;
  gx?: number;
  gy?: number;
  gz?: number;
}
```

---

# Batasan Interpretasi

Model MPU saat ini dapat mengklasifikasikan pola motorik menjadi:

```text
Parkinson Motor Pattern
```

atau:

```text
Healthy / Non-Parkinson-like Pattern
```

Namun, model ini belum dapat menyimpulkan:

```text
Stress Tremor
```

atau:

```text
Non-Stress Tremor
```

Alasannya: dataset motorik PADS tidak memiliki label stres. MPU6050 hanya mengukur gerakan, bukan kondisi stres fisiologis.

Interpretasi yang benar:

```text
NeuroFlow tidak menyimpulkan stres hanya dari getaran tangan. MPU6050 digunakan untuk membaca pola motorik dari akselerometer dan giroskop. Model menghasilkan skor yang dibandingkan dengan threshold hasil training. Untuk menentukan apakah tremor meningkat karena stres, sistem perlu menggabungkan output motorik dengan indikator fisiologis seperti heart rate dan HRV dari MAX30102.
```

---

# File yang Tidak Disarankan untuk Commit

Jangan commit file berikut:

```text
training/data/
training/reports/
ml_service/data/
ml_service/*.db
ml_service/models/*.joblib
ml_service/models/*.pkl
ml_service/models/*.onnx
ml_service/models/*.h5
ml_service/models/*.keras
frontend/node_modules/
frontend/.next/
.env
.env.local
```

File config model kecil boleh di-commit:

```text
ml_service/models/*_config.json
```

---

# Commit Workflow

Cek status:

```bash
git status
```

Stage file penting:

```bash
git add frontend ml_service/app training/*.py firmware .gitignore .dockerignore docker-compose.yml DOCKER_DEPLOYMENT.md
git add -f ml_service/models/*_config.json
```

Commit:

```bash
git commit -m "Integrate raw MPU model inference and telemetry pipeline"
```

Push:

```bash
git push origin feature/ml-service-pads-baseline-v2
```

---

# Limitasi Saat Ini

* Model masih baseline dan belum diagnosis medis final.
* Stress tremor belum bisa disimpulkan dari MPU6050 saja.
* Dataset PADS berasal dari smartwatch accelerometer/rotation, sedangkan NeuroFlow memakai MPU6050.
* Perlu kalibrasi dengan data real dari perangkat NeuroFlow.
* MAX30102 HR/HRV perlu diintegrasikan untuk stress-context inference.
* Model binary besar belum disimpan langsung di Git.

---

# Rencana Pengembangan

* Mengumpulkan dataset raw MPU6050 dari perangkat NeuroFlow.
* Membuat subject-level calibration.
* Menambahkan ekstraksi HRV dari MAX30102.
* Melatih model stress-context menggunakan dataset stres atau data eksperimen sendiri.
* Menyimpan riwayat hasil inference ke reports.
* Menambahkan Docker production profile.
* Menggunakan Git LFS atau model registry untuk menyimpan model binary.
* Menambahkan automated test untuk API dan feature extraction.

---

# Branch

```text
feature/ml-service-pads-baseline-v2
```

Branch ini berisi integrasi awal ML service, pipeline raw MPU6050, telemetry frontend, dan baseline Parkinson motor-pattern inference untuk NeuroFlow.

# NeuroFlow: Clinical Biometric Telemetry System

NeuroFlow is an end-to-end edge-to-cloud biometric analysis system designed to monitor motor patterns (tremors) and physiological stress context using the ESP32, MPU6050, and MAX30102 sensors.

## Clinical Interpretation Policy & Limitations

**NeuroFlow is not a medical diagnostic tool.** This system implements a strict, literature-aligned architecture to analyze biometric telemetry safely:

1. **Motor Pattern Analysis**: The MPU6050 accelerometer and gyroscope data is used exclusively for detecting rhythm, energy, and dominant frequencies associated with motor patterns (e.g., 4-6 Hz for Parkinson-like resting tremor, 8-12 Hz for physiologic tremor). 
2. **Stress Context**: The system **will not** diagnose physiological stress from MPU data alone. Heart Rate (HR) and Heart Rate Variability (HRV - RMSSD, SDNN, pNN50) from the MAX30102 sensor are used as the primary indicators of a physiological stress response.
3. **Stress-Amplified Tremor**: The system only outputs "Possible stress-amplified tremor" when both a valid narrow-band tremor is detected and physiological stress (elevated HR, low HRV) is actively occurring.
4. **Motion Artifact Rejection**: High-energy, low-frequency movements (Walking) and high-jerk, broad-spectrum movements (Typing) are strictly gated out. If the system detects these patterns, tremor analysis is suspended for that time window to prevent false positives.

## How to Run the Project

### 1. ESP32 Firmware (Edge Device)
- Open `firmware/NeuroFlow_Node/NeuroFlow_Node.ino` in the **Arduino IDE**.
- Install the required libraries: `Adafruit MPU6050`, `MAX30105`, and `PubSubClient`.
- Update the `ssid` and `password` variables to match your local WiFi network.
- Flash the code to your ESP32.

### 2. ML Service (Backend)
The Python FastAPI service handles complex frequency analysis and ML inference.
```bash
cd ml_service
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. Frontend Dashboard
The Next.js PWA displays real-time analysis and clinical interpretations.
```bash
cd frontend
npm install
npm run dev
```

### 4. Dummy Telemetry (Hardware Simulator)
If you don't have the physical ESP32 connected, you can run the dummy telemetry script to simulate 7 highly realistic clinical scenarios (Rest, Parkinson Tremor, Anxious Tremor, Typing, Walking, etc.).
```bash
cd ml_service
python dummy_telemetry.py
```
