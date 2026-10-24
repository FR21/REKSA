# Panduan Deployment REKSA

Panduan komprehensif arsitektur dan tata cara deployment REKSA pada lingkungan **Cloud Production (Compute Engine VM, Google Cloud Run, HiveMQ Cloud, & Firebase)**, **GitHub Actions CI/CD**, serta **Lokal (Docker Compose)**.

```text
               +-----------------------------+
               |      ESP32 Smart Helmet     |
               | (Sensor IMU, Gas, Suhu, Mic)|
               +--------------+--------------+
                              |
                     MQTTS TLS Port 8883
                   (ISRG Root X1 Cert)
                              v
               +-----------------------------+
               |     HiveMQ Cloud Cluster    |
               | (xxxxxx.s1.eu.hivemq.cloud) |
               +--------------+--------------+
                              |
               +--------------v--------------+
               |   Reksa Bridge (Compute VM) |
               | - Name: reksa-free-bridge   |
               | - Zone: us-central1-a       |
               | - Type: e2-micro            |
               | - Persistent MQTTS Gateway  |
               +--------------+--------------+
                              |
                     gRPC / HTTPS Push
                              v
               +-----------------------------+
               |     Google Cloud Pub/Sub    |
               |  (Topic: reksa-telemetry)   |
               +--------------+--------------+
                              |
                 Push Subscription Webhook
              (POST /api/v1/ingest/pubsub)
                              v
+-----------------------------+-----------------------------+
|               FastAPI Backend (Cloud Run)                 |
| - Near-Miss Detection Engine                              |
| - WebSocket Broadcaster (/ws/live)                        |
| - Speech NLU Processor (Wit.ai API)                       |
+--------------+------------------------------+--------------+
               |                             |
      SQLAlchemy (async)                     | WebSocket & HTTPS
               v                             v
+-----------------------------+ +---------------------------+
|    Neon Lakebase Postgres   | |      Firebase Hosting     |
| (Database Cloud Relasional) | | (React Dashboard Web App) |
| (Insiden, Personel, Audit)  | |  (https://reksa-k3.web.app)|
+-----------------------------+ +---------------------------+
```

> **Prinsip Keselamatan K3:** Seluruh aktuator alarm lokal helm (buzzer dan motor vibrasi) bekerja secara otonom pada chip ESP32 (< 20 ms). Gangguan jaringan internet atau downtime cloud **tidak mematikan** perlindungan bahaya fisik di lapangan.

---

## 1. Setup Broker HiveMQ Cloud (TLS Port 8883) — Panduan Pasti Fix

HiveMQ Cloud Serverless digunakan sebagai broker MQTT cloud publik terkelola untuk menghubungkan perangkat ESP32 di mana pun berada.

### A. Pembuatan Cluster & Hostname
1. Buka [HiveMQ Cloud Console](https://app.hivemq.com/) dan buat cluster baru (**Serverless - Free Tier**).
2. Salin URL Cluster pada dashboard HiveMQ (contoh: `abc123def456.s1.eu.hivemq.cloud`).
3. Port broker yang digunakan adalah **`8883`** dengan enkripsi **TLS/SSL**. (Port 1883 tidak aktif pada HiveMQ Cloud demi keamanan).

### B. Konfigurasi Kredensial Pengguna (Access Management)
Buka menu **Access Management → Credentials** pada konsol HiveMQ, buat 2 pengguna dengan hak akses penuh (*Publish & Subscribe*):
1. **Pengguna Helm:**
   * **Username:** `reksa-helmet-w01`
   * **Password:** *(buat password aman, misal: `HelmSafety2026!`)*
   * **Role:** *Publish and Subscribe*
2. **Pengguna Bridge (Compute Engine VM):**
   * **Username:** `reksa-bridge`
   * **Password:** *(buat password aman, misal: `BridgeCloudPass2026!`)*
   * **Role:** *Publish and Subscribe*

### C. Sertifikat TLS Root CA untuk ESP32
HiveMQ Cloud menggunakan sertifikat TLS yang diterbitkan oleh **Let's Encrypt (ISRG Root X1)**.
Untuk menyetelnya secara otomatis ke firmware ESP32:
```bash
chmod +x ./deploy/setup-hivemq.sh
./deploy/setup-hivemq.sh
```
Script tersebut akan mengambil rantai sertifikat TLS dari HiveMQ Cloud, mengekstrak root CA, dan langsung menulis berkas `arduino/helm_v1/secrets.h` yang siap di-flash ke ESP32.

### D. Verifikasi Koneksi Broker
Jalankan pengujian end-to-end broker sebelum deploy:
```bash
chmod +x ./deploy/test-hivemq.sh
./deploy/test-hivemq.sh
```
Jika berhasil, output akan menampilkan status *Connected* dan konfirmasi pesan publish/subscribe.

---

## 2. Arsitektur Cloud Production (GCP VM, Cloud Run, Firebase)

Di lingkungan produksi cloud, beban kerja didistribusikan secara efisien sesuai karakteristik protokol:

| Layanan | Platform | Konfigurasi Utama | Peran |
| :--- | :--- | :--- | :--- |
| **`reksa-bridge`** | Google Compute Engine (VM Instance) | **VM:** `reksa-free-bridge`<br>**Zone:** `us-central1-a`<br>**Type:** `e2-micro`<br>Debian 12 / Docker | Menjaga koneksi MQTTS TLS persisten 24/7 ke HiveMQ Cloud tanpa terputus (menghindari limitasi scale-to-zero serverless) dan mem-forward telemetri ke Cloud Pub/Sub via gRPC. |
| **`reksa-backend`** | Google Cloud Run | `--min-instances 0`<br>`--memory 1Gi`<br>`--cpu 1` | `MQTT_ENABLED=false`, menerima data dari webhook push Cloud Pub/Sub, memproses machine learning Near-Miss, menghubungkan Neon PostgreSQL, dan mengalirkan WebSocket ke web. Scale-to-zero hemat biaya. |
| **`reksa-ai`** | Google Cloud Run | `--min-instances 0`<br>`--memory 1Gi`<br>`--cpu 1`<br>`--cpu-throttling` | Microservice AI inferensi prediktif K3 (FastAPI + scikit-learn). Scale-to-zero ($0 saat idle). Melayani `/v1/forecast`, `/v1/prioritize`, `/v1/detect-anomaly`, dan `/health`. |
| **Frontend** | Firebase Hosting | Target: `reksa-k3`<br>CDN Global | Menampilkan web dashboard React Vite K3 (`https://reksa-k3.web.app`). |

### Efisiensi Biaya & Keandalan Koneksi:
1. **Bridge pada Compute Engine VM (`reksa-free-bridge` di `us-central1-a`):**
   * Protokol MQTT subscriber membutuhkan koneksi TCP persisten (*always-on long-lived connection*). Jika dijalankan di Cloud Run dengan scale-to-zero, kontainer akan mati saat idle sehingga pesan MQTT dari helm terlewat.
   * VM `e2-micro` pada zone `us-central1-a` dialokasikan khusus untuk menjaga koneksi listener MQTT dan meneruskan data ke Cloud Pub/Sub secara stabil dan hemat sumber daya.
2. **Backend & AI pada Cloud Run (`--min-instances 0`):**
   * Layanan `reksa-backend` dan `reksa-ai` berbasis HTTP/Webhook request-driven, sehingga disetel `--min-instances 0` agar kontainer otomatis tidur (*idle*) saat tidak ada event, menghasilkan tagihan komputasi **Rp 0 / $0**.

---

## 3. Deployment Otomatis via GitHub Actions CI/CD (Rekomendasi)

Repositori ini telah dilengkapi pipeline CI/CD GitHub Actions terotomatisasi di direktori `.github/workflows/`. Setiap kali Anda melakukan `git push origin master`, pipeline akan mendeteksi folder yang berubah dan melakukan deploy secara otomatis.

### A. Menyetel GitHub Repository Secrets
Buka repositori GitHub Anda di browser: **Settings → Secrets and variables → Actions**, lalu tambahkan *Repository Secrets* berikut:

| Nama Secret | Deskripsi / Contoh Nilai |
| :--- | :--- |
| `GCP_PROJECT_ID` | ID Project Google Cloud Anda (contoh: `reksa-safety`) |
| `FIREBASE_SERVICE_ACCOUNT` | Seluruh isi file JSON Service Account GCP dengan izin Cloud Run Admin, Pub/Sub Admin, & Firebase Admin |
| `DATABASE_URL` | Connection string Neon PostgreSQL (contoh: `postgresql://neondb_owner:***@ep-***.asia-southeast-2.aws.neon.tech/neondb?sslmode=require`) |
| `HIVEMQ_HOST` | Hostname broker HiveMQ Anda tanpa `mqtts://` (contoh: `abc123def456.s1.eu.hivemq.cloud`) |
| `HIVEMQ_USERNAME` | Username broker untuk bridge (contoh: `reksa-bridge`) |
| `HIVEMQ_PASSWORD` | Password broker untuk bridge |
| `PUBSUB_TOPIC` | Nama topik Pub/Sub (isi: `reksa-telemetry`) |
| `WIT_AI_TOKEN` | Token API server Wit.ai untuk NLU suara Bahasa Indonesia |
| `VITE_API_URL` | URL Cloud Run backend (contoh: `https://reksa-backend-***-et.a.run.app/api/v1`) |
| `VITE_WS_URL` | URL WebSocket Cloud Run backend (contoh: `wss://reksa-backend-***-et.a.run.app/ws/live`) |

### B. Cara Memicu Deploy Otomatis
* **Deploy Backend:** Lakukan perubahan/push pada folder `backend/**` $\to$ workflow `.github/workflows/deploy-backend.yml` akan berjalan.
* **Deploy AI Service:** Lakukan perubahan/push pada folder `AI/**` $\to$ workflow `.github/workflows/deploy-ai.yml` akan berjalan.
* **Deploy Frontend:** Lakukan perubahan/push pada folder `frontend/**` $\to$ workflow `.github/workflows/deploy-frontend.yml` akan berjalan.
* **Bridge (Compute Engine VM):** Layanan `reksa-bridge` berjalan persisten di Compute Engine VM instance (`reksa-free-bridge`, zone `us-central1-a`) agar koneksi MQTTS tidak terputus. Deploy/update dilakukan langsung di VM menggunakan Docker / systemd.
* **Deploy Manual:** Buka tab **Actions** di GitHub, pilih workflow yang ingin dijalankan, lalu klik tombol **Run workflow**.

---

## 4. Deployment Manual via Google Cloud CLI (Alternatif)

Jika Anda ingin melakukan deploy manual langsung dari terminal laptop:

### Prasyarat Terminal:
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project ID_PROJECT_GCP_ANDA
firebase login
```

### A. Deploy Reksa Bridge ke Google Compute Engine (VM Instance):

1. **Buat Service Account & Izin Pub/Sub untuk Bridge:**
```bash
gcloud iam service-accounts create reksa-bridge \
  --display-name="REKSA Bridge Gateway" || true

gcloud pubsub topics add-iam-policy-binding reksa-telemetry \
  --member="serviceAccount:reksa-bridge@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

2. **Buat VM Instance di Compute Engine (`reksa-free-bridge` di `us-central1-a`):**
```bash
gcloud compute instances create reksa-free-bridge \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --service-account="reksa-bridge@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --scopes=cloud-platform \
  --tags=reksa-bridge
```

3. **Deploy Container Bridge di dalam VM:**
```bash
# SSH ke VM reksa-free-bridge dan siapkan container Docker
gcloud compute ssh reksa-free-bridge --zone=us-central1-a --command="
  sudo apt-get update && sudo apt-get install -y docker.io git
  sudo systemctl enable --now docker
  sudo mkdir -p /opt/reksa-bridge /var/data/reksa
"

# Salin folder bridge dan file environment ke VM
gcloud compute scp --recurse bridge reksa-free-bridge:/opt/reksa-bridge --zone=us-central1-a

# Konfigurasikan /opt/reksa-bridge/bridge/.env di VM:
# GOOGLE_CLOUD_PROJECT=ID_PROJECT_GCP_ANDA
# PUBSUB_TOPIC=reksa-telemetry
# MQTT_HOST=abc123def456.s1.eu.hivemq.cloud
# MQTT_PORT=8883
# MQTT_USERNAME=reksa-bridge
# MQTT_PASSWORD=PasswordBridgeAnda
# BRIDGE_ID=reksa-gateway-01

# Bangun dan jalankan kontainer bridge secara persisten (Always-On)
gcloud compute ssh reksa-free-bridge --zone=us-central1-a --command=\"
  cd /opt/reksa-bridge/bridge
  sudo docker build -t reksa-bridge .
  sudo docker rm -f reksa-bridge || true
  sudo docker run -d --name reksa-bridge \\
    --restart always \\
    --env-file .env \\
    -v /var/data/reksa:/data \\
    reksa-bridge
\"
```

### B. Deploy FastAPI Backend ke Cloud Run:
```bash
cat << 'EOF' > backend/env.yaml
APP_ENV: "production"
MQTT_ENABLED: "false"
DATABASE_URL: "postgresql+psycopg://neondb_owner:***@ep-***.asia-southeast-2.aws.neon.tech/neondb?sslmode=require"
WIT_AI_TOKEN: "Bearer ***"
CORS_ORIGINS: "https://reksa-k3.web.app,https://ID_PROJECT_GCP_ANDA.web.app,http://localhost:5173"
EOF

gcloud run deploy reksa-backend \
  --source backend \
  --region asia-southeast2 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 2 \
  --env-vars-file backend/env.yaml
```

### C. Deploy Reksa AI ke Cloud Run:
```bash
gcloud run deploy reksa-ai \
  --source AI \
  --region asia-southeast2 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --cpu-throttling \
  --min-instances 0 \
  --max-instances 1
```

### D. Sambungkan Google Cloud Pub/Sub ke Backend:
```bash
# 1. Buat Topic Pub/Sub
gcloud pubsub topics create reksa-telemetry || true

# 2. Ambil URL Backend Cloud Run
BACKEND_URL="$(gcloud run services describe reksa-backend --region asia-southeast2 --format='value(status.url)')"

# 3. Buat Push Subscription yang mengalirkan pesan ke webhook FastAPI
gcloud pubsub subscriptions create reksa-cloud-run-push \
  --topic=reksa-telemetry \
  --push-endpoint="${BACKEND_URL}/api/v1/ingest/pubsub" \
  --ack-deadline=30 || true
```

### E. Build & Deploy Frontend ke Firebase Hosting:
```bash
cd frontend
VITE_API_URL="${BACKEND_URL}/api/v1" VITE_WS_URL="${BACKEND_URL/https:/wss:}/ws/live" npm run build
firebase deploy --only hosting:reksa-k3
```

---

## 5. Deployment Lokal (Pengujian Offline / Docker Compose)

Untuk keperluan simulasi, presentasi offline, atau pengembangan lokal tanpa koneksi internet ke GCP:

```bash
# 1. Jalankan semua kontainer lokal (Postgres, Mosquitto, AI, Backend, Frontend)
docker compose up --build -d

# 2. Cek status container
docker compose ps

# 3. Akses dashboard di browser
http://localhost:5173
```

Layanan lokal akan berjalan di port:
* Frontend: `http://localhost:5173`
* Backend API: `http://localhost:8000` (Docs di `/docs`)
* AI Service: `http://localhost:8100`
* MQTT Mosquitto: `localhost:1883`
* PostgreSQL: `localhost:5432`

---

## 6. Verifikasi & Pengujian End-to-End

Setelah deployment selesai, lakukan pemeriksaan integritas sistem:

1. **Uji Status Bridge di Compute Engine VM (`reksa-free-bridge`):**
   ```bash
   gcloud compute ssh reksa-free-bridge --zone=us-central1-a --command="docker ps"
   # Menampilkan container reksa-bridge dengan status Up
   ```
2. **Uji Health Check Backend:**
   ```bash
   curl -fsS https://reksa-backend-***-et.a.run.app/api/v1/health
   # Output: {"status":"healthy", ...}
   ```
3. **Uji Health Check AI Service:**
   ```bash
   curl -fsS https://reksa-ai-***-et.a.run.app/health
   # Output: {"status":"healthy","service":"reksa-ai","models_loaded":true}
   ```
4. **Uji Transmisi Telemetri Helm:**
   * Nyalakan ESP32 yang sudah diprogram dengan `secrets.h`.
   * Periksa log container Bridge pada Compute Engine VM:
     ```bash
     gcloud compute ssh reksa-free-bridge --zone=us-central1-a --command="docker logs -f reksa-bridge"
     ```
   * Pastikan muncul pesan log:
     `Connected to HiveMQ and subscribed`
     `Buffered HELMET-W01-... from REKSA/helmet/W01/sensor`
     `Forwarded HELMET-W01-... to Pub/Sub as ...`
5. **Pantau Dashboard Web:**
   * Buka `https://reksa-k3.web.app`.
   * Status pekerja `W01` otomatis berubah menjadi hijau (**Online**), dan indikator sensor (suhu, IMU, gas) terupdate secara real-time melalui WebSocket.
