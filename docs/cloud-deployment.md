# REKSA Cloud Upload Guide

> Untuk panduan operasional yang bisa diikuti dari nol dan berisi perintah siap
> salin-tempel, gunakan [`PANDUAN-DEPLOY-STEP-BY-STEP.md`](../PANDUAN-DEPLOY-STEP-BY-STEP.md).

Arsitektur final mempertahankan alarm di ESP32. HiveMQ, bridge, Pub/Sub, Cloud Run,
Firestore, dan Firebase hanya berada pada jalur telemetry, AI advisory, dan dashboard.

## 1. HiveMQ Cloud TLS

1. Buat cluster HiveMQ Cloud Serverless.
2. Buat kredensial terpisah untuk `reksa-helmet-w01`, `reksa-backend`, dan
   `reksa-gateway-01`; jangan memakai satu password untuk seluruh perangkat.
3. Batasi helmet agar hanya boleh publish `REKSA/helmet/W01/sensor`, subscribe
   `REKSA/helmet/W01/warning`, dan subscribe `REKSA/helmet/W01/telemetry/ack`.
4. Salin `arduino/helm_v1/secrets.example.h` menjadi `secrets.h`, lalu isi endpoint,
   port `8883`, username, password, dan root CA. Jangan memakai `setInsecure()`.
5. Salin `.env.hivemq.example` menjadi `.env.hivemq`, lalu jalankan:

```bash
docker compose --env-file .env.hivemq -f docker-compose.yml -f docker-compose.hivemq.yml up --build
```

Firmware menyimpan maksimal 12 payload di RAM dan mengirim ulang setiap tiga detik
sampai backend atau bridge mengirim ACK. Backend menyimpan cache ID terakhir untuk
mencegah retransmission diproses dua kali.

## 2. Bukti disconnect, reconnect, dan retransmission

1. Jalankan helmet sampai serial monitor menampilkan `Telemetry diterima`.
2. Putuskan Wi-Fi selama 15-20 detik dan tetap gerakkan helmet pada skenario uji.
3. Catat `message_id`, jumlah buffer, dan `dropped` pada serial monitor.
4. Sambungkan Wi-Fi kembali.
5. Buktikan ID lama dikirim dengan `attempt > 1`, ACK diterima, dan backend hanya
   membuat satu record/event untuk setiap ID.

Simpan video serial monitor, log backend, waktu putus/sambung, jumlah generated,
buffered, resent, acknowledged, duplicate, dan dropped. Klaim `zero data loss` hanya
boleh digunakan bila `dropped=0` pada seluruh pengulangan.

Ekspor serial monitor ke file dan hitung bukti latency/alarm offline:

```bash
python tools/analyze_firmware_metrics.py evidence/serial-run-01.log
```

## 3. Google Cloud dan Firebase

Prasyarat: project Firebase/GCP yang sama, billing aktif dengan budget alert, `gcloud`,
Firebase CLI, dan Node.js. Login terlebih dahulu:

```bash
gcloud auth login
gcloud auth application-default login
firebase login
```

Deploy layanan AI, backend stateless, Firestore, Pub/Sub push, lalu dashboard:

```bash
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=asia-southeast2
./deploy/gcp/deploy.sh
```

Script mengatur `MQTT_ENABLED=false` pada Cloud Run. Cloud Run tidak memelihara
subscriber MQTT; pesan masuk melalui Pub/Sub push ke `/api/v1/ingest/pubsub`.
Raw envelope disimpan ke Firestore untuk audit. SQLite `/tmp` hanya dipakai oleh seed
dashboard dan bukan sumber data persisten.

## 4. Menjalankan bridge

Untuk development tanpa service-account key:

```bash
cd bridge
cp .env.example .env
set -a
. ./.env
set +a
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m reksa_bridge
```

Untuk gateway Docker, simpan service-account JSON terbatas di
`secrets/gcp-service-account.json`, isi `bridge/.env`, lalu:

```bash
mkdir -p secrets
gcloud iam service-accounts keys create secrets/gcp-service-account.json \
  --iam-account="reksa-bridge@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
docker compose -f docker-compose.bridge.yml up --build
```

Key JSON hanya dipakai bila gateway tidak mendukung Application Default Credentials.
Rotasi/hapus key setelah lomba dan jangan pernah memasukkannya ke Git.

Bridge memasukkan pesan ke SQLite sebelum mencoba Pub/Sub. Hanya setelah Pub/Sub
mengembalikan message ID, bridge menghapus outbox dan mengirim ACK ke helmet.

## 5. Verifikasi setelah deploy

```bash
curl "$BACKEND_URL/api/v1/health"
curl "$AI_URL/health"
gcloud pubsub topics publish reksa-telemetry --message='{"topic":"REKSA/test/status","payload":{"message_id":"smoke-1"}}'
gcloud run services logs read reksa-backend --region asia-southeast2 --limit 50
```

Gunakan endpoint dan project ID yang dicetak `deploy.sh`. Jangan unggah `.env`,
`secrets.h`, service-account JSON, atau password HiveMQ ke Git/GEMASTIK.
