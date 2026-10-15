# Panduan Deployment REKSA

Panduan konfigurasi dan deployment REKSA pada lingkungan **Lokal (Docker)**, **Broker HiveMQ Cloud (TLS)**, dan **Cloud Production (GCP & Firebase)**.

```text
               +-------------------+
               | ESP32 IoT Helmets |
               +---------+---------+
                         |
           (MQTTS TLS / Port 8883)
                         v
               +-------------------+
               |   HiveMQ Cloud    |
               +---------+---------+
                         |
           +-------------+-------------+
           | (Bridge / Outbox Pattern) |
           +-------------+-------------+
                         v
               +-------------------+
               |  GCP Cloud Pub/Sub|
               +---------+---------+
                         |
         +---------------+---------------+
         |                               |
         v                               v
+-----------------+             +-----------------+
| Cloud Run (API) | <---------> | Cloud Run (AI)  |
+--------+--------+             +-----------------+
         |
         v
+-----------------+
| Firebase Hosting| (Frontend React Dashboard)
+-----------------+
```

> **Catatan K3:** Alarm fisik (buzzer & vibrasi) pada helm ESP32 beroperasi mandiri (*autonomous*). Pemutusan internet atau cloud outage tidak menghentikan fungsi perlindungan K3 lokal di helm.

---

## 1. Deployment Lokal (Docker Compose)

Langkah tercepat untuk menjalankan seluruh ekosistem REKSA di laptop/server lokal.

### Prasyarat
- Docker Engine $\ge 24.0$ & Docker Compose v2
- Port yang harus tersedia: `5173` (Frontend), `8000` (Backend API), `8100` (AI Service), `1883` (MQTT Mosquitto), `9001` (MQTT WS), `5432` (PostgreSQL).

### Langkah Eksekusi
```bash
# 1. Jalankan seluruh container
docker compose up --build -d

# 2. Periksa status kesehatan container
docker compose ps

# 3. Uji endpoint API
curl -fsS http://localhost:8000/api/v1/health
curl -fsS http://localhost:8100/health
```

Buka dashboard di peramban: `http://localhost:5173`.

Untuk memantau log secara live:
```bash
docker compose logs -f backend ai
```

---

## 2. Konfigurasi HiveMQ Cloud (TLS Port 8883)

Untuk pengujian helm fisik di luar jaringan LAN lokal menggunakan broker MQTT cloud publik.

### A. Setup Broker HiveMQ
1. Buat akun di [HiveMQ Cloud](https://app.hivemq.com/) dan buat broker paket **Serverless** (gratis).
2. Salin hostname cluster (contoh: `xxxxxx.s1.eu.hivemq.cloud`).
3. Pada tab **Access Management → Credentials**, buat tiga akun kredensial terpisah:
   - **Backend:** Username `reksa-backend` (Role: *Publish and Subscribe*)
   - **Helmet:** Username `reksa-helmet-w01` (Role: *Publish and Subscribe*)
   - **Gateway/Bridge:** Username `reksa-gateway-01` (Role: *Publish and Subscribe*)

### B. Konfigurasi Firmware Helm (`arduino/helm_v1/`)
1. Salin `arduino/helm_v1/secrets.example.h` menjadi `arduino/helm_v1/secrets.h`.
2. Isi SSID WiFi, Password, Hostname HiveMQ, port `8883`, dan kredensial `reksa-helmet-w01`.
3. Set `#define REKSA_MQTT_USE_TLS true` dan pastikan root CA terpasang (jangan gunakan mode insecure).
4. Flash firmware ke ESP32.

### C. Menjalankan Backend dengan HiveMQ
Salin konfigurasi environment:
```bash
cp .env.hivemq.example .env.hivemq
# Edit .env.hivemq dan masukkan broker host & credentials
docker compose --env-file .env.hivemq -f docker-compose.yml -f docker-compose.hivemq.yml up --build -d
```

---

## 3. Deployment Production (GCP & Firebase)

Arsitektur produksi cloud menempatkan backend dan AI service di **Google Cloud Run**, data telemetri melalui **Cloud Pub/Sub**, dan frontend di **Firebase Hosting**.

### Prasyarat
- Google Cloud SDK (`gcloud`) terinstal dan terautentikasi:
  ```bash
  gcloud auth login
  gcloud auth application-default login
  firebase login
  ```
- Project GCP dengan billing aktif.

### Deployment Script Otomatis
```bash
export GCP_PROJECT_ID="id-project-anda"
export GCP_REGION="asia-southeast2"

# Jalankan deploy pipeline
chmod +x ./deploy/gcp/deploy.sh
./deploy/gcp/deploy.sh
```

Script ini otomatis melakukan:
1. Build & push container image `reksa-backend` dan `reksa-ai` ke Artifact Registry / Container Registry.
2. Deploy backend ke Cloud Run dengan flag `MQTT_ENABLED=false` (Cloud Run menerima data via Pub/Sub push HTTP webhook ke `/api/v1/ingest/pubsub`).
3. Setup topic & subscription Pub/Sub.
4. Build bundle frontend React dan deploy ke Firebase Hosting.

---

## 4. Menjalankan MQTT Bridge (Edge Gateway)

Bridge bertugas menjembatani pesan MQTT dari HiveMQ Cloud ke Google Cloud Pub/Sub dengan outbox SQLite lokal agar tidak ada data yang hilang saat internet gateway terputus.

### Menjalankan via Docker Gateway:
```bash
mkdir -p secrets
# Buat service account key terbatas untuk bridge
gcloud iam service-accounts keys create secrets/gcp-service-account.json \
  --iam-account="reksa-bridge@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

cp bridge/.env.example bridge/.env
# Isi kredensial pada bridge/.env
docker compose -f docker-compose.bridge.yml up --build -d
```

---

## 5. Verifikasi Uji Ketahanan Sinyal (Zero Data Loss)

Untuk membuktikan ketahanan sistem saat pekerja berada di area blank spot:

1. Nyalakan helm hingga terhubung ke broker (`Serial Monitor: Telemetry masuk buffer... attempt=1`).
2. Matikan router Wi-Fi selama 15–30 detik sambil tetap menggerakkan helm.
3. Amati Serial Monitor: payload tersimpan di antrean RAM internal helm (`telemetryQueue`, kapasitas 12 payload).
4. Nyalakan kembali Wi-Fi.
5. Konfirmasi bahwa seluruh payload yang tertunda dikirim ulang dengan `attempt > 1`, menerima `ACK` dari server, dan backend mendeduplikasi ID pesan tanpa data dobel.
