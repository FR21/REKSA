# REKSA

**Radar Evaluasi K3 dan Sensor Ancaman Kerja**  
Sistem pemantauan K3 (Keselamatan dan Kesehatan Kerja) berbasis IoT dan AI untuk lingkungan industri.

Intinya, REKSA ngebantu mantau risiko pekerja yang beraktivitas di dekat alat berat (seperti forklift) secara *real-time*. Sistem ini punya command center dashboard, tracking sensor fisik pekerja, deteksi *near-miss* otomatis, sampai peringatan bahaya yang dikirim langsung ke *smart helmet*.

> **Note:** Secara default, sistem pakai data simulasi kalau hardware nggak konek. Skor risiko dihitung berdasarkan kombinasi pembacaan sensor IoT dan AI predictive model (Random Forest).

## Arsitektur

Secara garis besar, alurnya seperti ini:

```mermaid
flowchart LR
  I[Smart Helmet (ESP32) / Simulator] -->|MQTT| M[Mosquitto]
  M --> B[FastAPI Backend]
  B <--> D[(PostgreSQL)]
  B -->|REST + WebSocket| R[React Command Center]
  R -->|Config / Action| B
```

Dokumentasi lebih detail soal arsitektur, API, dan kontrak MQTT bisa dicek di folder `docs/`.

## Tech Stack

- **Frontend:** React 19, Vite, TypeScript, TanStack Query, Zustand, Recharts.
- **Backend:** FastAPI, SQLAlchemy, Alembic, paho-mqtt.
- **AI / Data Science:** Scikit-learn, Pandas (Model AI eksperimen ada di `Reksa_AI.ipynb`).
- **IoT / Hardware:** ESP32/ESP8266 dengan library BLE & WiFi (kodenya ada di folder `arduino/`).
- **Infra:** Docker, PostgreSQL 17, Eclipse Mosquitto (MQTT Broker).

## Cara Jalanin di Lokal

Syarat:
- Udah install Docker & Docker Compose v2.
- Port 5173, 8000, 1883, dan 9001 pastikan lagi kosong / gak dipake aplikasi lain.

### Pake Docker (Paling Gampang)

Tinggal jalankan command ini di root project:
```bash
docker compose up --build
```
Selesai. Tinggal buka `http://localhost:5173` di browser. API docs-nya ada di `http://localhost:8000/docs`.

### Cara Manual (Tanpa Docker)

Kalau mau *run* manual buat *development*:

1. **Jalanin Backend**
```bash
python -m venv .venv
source .venv/bin/activate  # Kalau di Windows pakenya: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env

cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

2. **Jalanin Frontend** (buka tab terminal baru)
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

*Fyi, kalau jalanin manual gini, backend otomatis bakal pake SQLite dari settingan `.env.example`. Kalo pake Docker otomatis konek ke PostgreSQL.*

## Struktur Project

Berikut folder-folder utama di repo ini biar gampang nyarinya:

```text
reksa/
├── arduino/        # Kode firmware (C++) untuk smart helmet ESP32 & node forklift
├── backend/        # REST API & WebSocket server (FastAPI)
├── frontend/       # Dashboard UI (React)
├── mosquitto/      # Config MQTT broker
├── docs/           # Dokumentasi (Architecture, MQTT topics, dll)
├── Reksa_AI.ipynb  # Eksperimen model AI & Machine Learning
└── docker-compose.yml
```

## Setup Hardware IoT (ESP32)

Kalau kamu mau nyoba pake device / hardware asli:
1. Masuk ke folder `arduino/`.
2. Buka `helm_v1.ino` (buat dipasang di smart helmet) atau `hazard_forklift_f01.ino` (buat node hazard/alat berat).
3. Jangan lupa ganti `YOUR_WIFI_SSID`, `YOUR_WIFI_PASSWORD`, dan IP `MQTT_SERVER` di dalam kode sesuai jaringan lokal kamu.
4. Upload kodenya ke ESP32.

Helm nanti bakal ngirim data seperti suhu, impact (benturan), kualitas udara, dan kedekatan dengan alat berat (RSSI) via MQTT ke backend secara *live*.
