# REKSA (Radar Evaluasi K3 dan Sensor Ancaman Kerja)

Sistem keselamatan kerja industri berbasis IoT Smart Helmet dan web dashboard real-time. REKSA mendeteksi kedekatan pekerja terhadap alat berat (forklift, AGV, crane) dan mesin stasioner (press, CNC, laser cutter) menggunakan BLE RSSI, memantau telemetri fisik pekerja (jatuh bebas, benturan, suhu/kelembapan, kualitas udara), menyediakan saklar kontrol daya ON/OFF hemat baterai serta pengenalan perintah suara darurat (Voice NLU), serta mencatat insiden *near-miss* ke database untuk audit K3.

> **Prinsip Keselamatan Utama:** Alarm fisik (buzzer & vibrasi) di helm ESP32 beroperasi mandiri (*autonomous* pada tingkat firmware). Putusnya koneksi internet atau cloud server tidak mematikan fungsi perlindungan jarak aman di helm.

---

## Fitur Utama

- **Deteksi Kedekatan Otomatis & 5 Tingkat Risiko K3:**
  - Pemindaian BLE beacon mesin bergerak (Forklift/AGV) dan stasioner (Press/Laser) dengan kalkulasi rata-rata bergerak RSSI untuk memicu buzzer dan vibrasi helm seketika.
  - 5 Status Risiko K3 Terstandarisasi: **Aman / Safe**, **Moderat / Moderate**, **Tinggi / High**, **Kritis / Critical**, dan **Pemulihan / Recovery**.
- **Mode Pemulihan (Recovery Mode):**
  - Transisi status saat pekerja keluar dari zona bahaya atau ditandai aman oleh pengawas. Kondisi aman dipertahankan, alarm lokal helm dihentikan seketika, status insiden ditutup, dan durasi paparan dihitung otomatis untuk audit K3.
- **Deteksi & Tampilan Perangkat Offline (Standby Mode):**
  - Saat helm tidak terhubung atau dimatikan via switch daya ON/OFF, dashboard detail pekerja otomatis beralih ke state standby/offline khusus (AI Advisory ditangguhkan, indikator anomali beralih ke standby tanpa metrik semu, dan panduan tindakan pengawas menampilkan verifikasi APD & baterai).
- **Telemetri Sensor K3 (Smart Helmet Node):**
  - IMU MPU-6050: Deteksi jatuh bebas (*free-fall*) dan benturan kepala (*high-G impact*).
  - DHT22: Pemantauan heat stress (suhu tinggi & kelembapan ekstrem).
  - MQ-135: Deteksi gas berbahaya / kualitas udara buruk di area kerja.
- **Voice NLU:** Saklar kontrol daya fisik mengaktifkan/menonaktifkan operasional helm seketika (*standby mode* hemat energi). Mikrofon digital I2S (INMP441) menangkap audio transmisi suara darurat, ditranskripsi oleh Wit.ai untuk mengenali intent darurat (evakuasi, SOS medis, stop mesin, laporan bahaya) secara otomatis.
- **Web Dashboard Operasional:**
  - Peta live monitoring visual dengan grid posisi pekerja dan hazard.
  - Manajemen insiden near-miss dengan form investigasi supervisor & verifikasi CAPA (*Corrective and Preventive Action*).
  - Registrasi perangkat IoT (Smart Helmet, Mobile Hazard, Stationary Hazard, Node Lingkungan).
  - Audio playback rekaman transmisi suara darurat langsung dari dashboard.
  - Dukungan dwibahasa penuh (Bahasa Indonesia & English) via toggle di header.
- **Predictive Near-Miss Advisory (AI Service):** Tiga engine machine learning (FastAPI + scikit-learn) di port `8100`:
  1. *Near-Miss Risk Forecaster*: Prediksi pendekatan tidak aman 3–5 detik ke depan dari jendela temporal BLE-RSSI + IMU.
  2. *Operational Anomaly Detector (Isolation Forest)*: Deteksi anomali pola getaran dan sinyal telemetri sensor.
  3. *AI Priority Engine*: Penentuan prioritas investigasi antrean insiden K3 supervisor.

---

## Arsitektur Sistem

```text
       +---------------------------------------------+
       |           ESP32 Smart Helmet Node           |
       |  [MPU-6050] [DHT22] [MQ-135] [INMP441 Mic]  |
       |   [Buzzer] [Vibration] [Power Switch ON/OFF]|
       +----------------------+----------------------+
                              |
               (MQTT / MQTTS Port 1883 / 8883)
                              v
       +---------------------------------------------+
       |         MQTT Broker (Mosquitto / HiveMQ)    |
       +----------------------+----------------------+
                              |
                              v
       +---------------------------------------------+
       |               FastAPI Backend               |
       |  - MQTT Handler & Telemetry Ingestion       |
       |  - Voice NLU & Speech Transcription         |
       |  - PostgreSQL Database (Neon / Local)       |
       |  - WebSocket Live Stream (/ws/live)         |
       +-----------+---------------------+-----------+
                   |                     |
                   v                     v
       +---------------------+   +---------------------+
       |    AI Service       |   |   React Dashboard   |
       |  (Near-Miss Forecast|   |  (Vite + TypeScript |
       |   & Priority Engine)|   |   Tailwind-free CSS)|
       +---------------------+   +---------------------+
```

---

## Struktur Repositori

```text
reksa/
├── arduino/                   # Firmware ESP32
│   ├── helm_v1/               # Smart helmet firmware (sensor, BLE scan, audio stream, alarm)
│   ├── hazard_forklift_f01/   # Firmware beacon BLE untuk forklift (alat berat bergerak)
│   └── hazard_stationary_l01/ # Firmware beacon BLE untuk mesin stasioner (press, laser)
├── backend/                   # REST API & Layanan Inti (FastAPI)
│   ├── app/api/v1/            # Router API (workers, hazards, near-misses, devices, voice)
│   ├── app/core/              # Konfigurasi aplikasi & environment variables
│   ├── app/database/          # Skema SQLAlchemy, migrasi Alembic, dan initial seed
│   ├── app/services/          # Handler MQTT, proximity, voice NLU, database persistence
│   └── tests/                 # Unit & integration tests backend (pytest)
├── frontend/                  # Dashboard Monitoring (React + Vite + TypeScript)
│   ├── src/pages/             # Overview, Live Monitoring, Workers, Near-Misses, Settings
│   ├── src/components/        # Reusable UI components (Panel, Cards, VoicePlayer, Modal)
│   ├── src/i18n/              # Terjemahan antarmuka (id.ts & en.ts)
│   └── tests/                 # Unit tests frontend (Vitest)
├── AI/                        # Layanan Advisory Prediktif (FastAPI + scikit-learn)
│   ├── src/reksa_ai/          # Pipeline fitur, inferensi model, dan service HTTP
│   └── models/                # Bobot model terlatih (.joblib)
├── bridge/                    # Gateway MQTT ke GCP Cloud Pub/Sub (Compute Engine VM / Docker)
├── deploy/                    # Skrip pengujian & deployment (GCP, HiveMQ)
├── docs/                      # Dokumentasi teknis lengkap
│   ├── architecture.md        # Arsitektur detail & fail-safe design
│   ├── deployment.md          # Panduan deployment (GCE VM, Cloud Run, Firebase, Docker)
│   ├── mqtt-topics.md         # Spesifikasi kontrak topik MQTT & skema payload
│   └── sensor_output.md       # Pinout ESP32, log serial debugging, & threshold K3
├── docker-compose.yml         # Konfigurasi container lokal (postgres, mosquitto, ai, backend, frontend)
├── .env.example               # Contoh konfigurasi seluruh environment variables
└── Makefile                   # Shortcut perintah praktis (up, down, test, lint)
```

---

## Kebutuhan Sistem

- **Docker & Docker Compose:** Docker Engine $\ge 24.0$ dan Docker Compose v2.
- **Pengembangan Mandiri (tanpa Docker):**
  - Python 3.11 – 3.13
  - Node.js $\ge 20$ (disarankan Node.js 22 LTS)
  - Mosquitto MQTT Broker (port `1883`)
  - PostgreSQL 16+ (atau gunakan SQLite lokal bawaan)

---

## Panduan Menjalankan Sistem

### 1. Menjalankan Cepat dengan Docker Compose (Direkomendasikan)

1. Salin berkas konfigurasi environment:
   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```

2. Bangun dan jalankan seluruh container:
   ```bash
   docker compose up --build -d
   ```

3. Periksa status layanan:
   ```bash
   docker compose ps
   ```

Layanan yang aktif:
- **Web Dashboard:** [http://localhost:5173](http://localhost:5173)
- **Backend API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **AI Advisory Service:** [http://localhost:8100/health](http://localhost:8100/health)
- **Mosquitto MQTT Broker:** `localhost:1883` (TCP) dan `localhost:9001` (WebSocket)

Untuk menghentikan layanan:
```bash
docker compose down
```

---

### 2. Pengembangan Lokal (Bare-Metal)

#### A. Backend (FastAPI)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Jalankan migrasi database
alembic upgrade head

# Jalankan server API (port 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### B. Frontend (React + Vite)
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
Dashboard akan terbuka di `http://localhost:5173`.

#### C. AI Service
```bash
cd AI
pip install -e .
uvicorn reksa_ai.service:app --host 0.0.0.0 --port 8100 --reload
```

---

## Konfigurasi Environment Variables

Seluruh variabel lingkungan telah dikumpulkan dan didokumentasikan pada [`.env.example`](.env.example). Beberapa variabel utama:

| Variabel | Deskripsi | Default / Contoh |
| :--- | :--- | :--- |
| `DATABASE_URL` | URL koneksi basis data PostgreSQL atau SQLite | `postgresql://reksa:reksa_dev_password@localhost:5432/reksa` |
| `MQTT_HOST` | Host broker MQTT | `localhost` (atau endpoint HiveMQ Cloud) |
| `MQTT_PORT` | Port broker MQTT | `1883` (non-TLS) / `8883` (TLS) |
| `MQTT_TLS` | Aktifkan TLS untuk koneksi broker cloud | `false` / `true` |
| `AI_SERVICE_URL` | Endpoint HTTP layanan inferensi AI | `http://localhost:8100` |
| `WIT_AI_TOKEN` | Token API server Wit.ai untuk NLU perintah suara darurat | `Bearer <YOUR_TOKEN>` |
| `VITE_API_URL` | Base URL REST API untuk dashboard frontend | `http://localhost:8000/api/v1` |
| `VITE_WS_URL` | URL WebSocket real-time untuk dashboard | `ws://localhost:8000/ws/live` |

---

## Konfigurasi Hardware ESP32

1. Buka file [arduino/helm_v1/secrets.example.h](arduino/helm_v1/secrets.example.h).
2. Salin menjadi `arduino/helm_v1/secrets.h`:
   ```bash
   cp arduino/helm_v1/secrets.example.h arduino/helm_v1/secrets.h
   ```
3. Konfigurasikan SSID Wi-Fi, password, serta alamat IP/Host broker MQTT.
4. Buka `arduino/helm_v1/helm_v1.ino` pada Arduino IDE atau PlatformIO.
5. Pastikan modul ESP32 terhubung dan flash program pada baud rate `115200`.
6. Untuk node hazard forklift dan mesin stasioner, flash firmware masing-masing di folder `arduino/hazard_forklift_f01` dan `arduino/hazard_stationary_l01`.

Detail wiring diagram dan pemetaan pin GPIO dapat dilihat di [docs/sensor_output.md](docs/sensor_output.md).

---

## Pengujian & Kualitas Kode

Sistem dilengkapi pengujian unit komprehensif pada backend maupun frontend.

```bash
# Menjalankan seluruh pengujian unit
make test

# Menjalankan linter dan validasi build statis
make lint
```

Pengujian individual:
- **AI Service Tests:** `pytest AI/tests` (7 passed)
- **Backend Tests:** `pytest backend/tests` (40 passed)
- **Backend Linting:** `ruff check .` (Clean, PEP8 compliant)
- **Frontend Tests:** `npm test` (6 passed)
- **Frontend Linting & Typecheck:** `npm run lint && npm run build` (Clean, 0 errors)

---

## Referensi Dokumentasi

- [Arsitektur Sistem & Fail-Safe](docs/architecture.md)
- [Panduan Deployment Cloud & Produksi](docs/deployment.md)
- [Spesifikasi Sensor, Hardware, & Threshold K3](docs/sensor_output.md)
- [Spesifikasi Kontrak & Topik MQTT](docs/mqtt-topics.md)
- [Dokumentasi REST & WebSocket API](docs/api.md)
