# Panduan REKSA: dari laptop sampai HiveMQ dan Google Cloud

Ikuti urutan ini dari atas ke bawah. Jangan lompat langkah. Setiap langkah memiliki
bagian **Berhasil jika**. Kalau hasilmu berbeda, berhenti di langkah itu dan kirimkan
output terminalnya—jangan lanjut agar sumber error tidak bercampur.

Arsitektur yang dipasang:

```text
ESP32 --TLS/QoS 1--> HiveMQ Cloud --> bridge + outbox --> Pub/Sub
                                                          |
                                                          v
Firebase Hosting <-- dashboard <-- Cloud Run backend <-- Cloud Run AI
```

Alarm benturan, jatuh, gas, dan kedekatan tetap berjalan di ESP32 ketika internet
putus. Cloud dan AI hanya menambah pencatatan, dashboard, prioritas, dan prediksi.

## Langkah 1 — Masuk ke folder proyek

Buka terminal baru, lalu salin seluruh blok ini:

```bash
cd '/home/wielio/Documents/Wiefran/Proyek/REKSA/REKSA'
pwd
git status --short
```

**Berhasil jika:** `pwd` menampilkan folder yang berakhir dengan `/REKSA/REKSA`.
Perubahan pada `git status` tidak perlu dihapus karena itu adalah pekerjaan proyekmu.

## Langkah 2 — Pastikan Docker lokal sehat

Jalankan:

```bash
docker compose up --build -d
docker compose ps
curl -fsS http://localhost:8000/api/v1/health
curl -fsS http://localhost:8100/health
```

Buka dashboard lokal di <http://localhost:5173>.

**Berhasil jika:** status container `healthy`/`running`, kedua perintah `curl`
menghasilkan respons sehat, dan dashboard terbuka. Log health check berulang setiap
10 detik seperti yang sebelumnya terlihat adalah normal, bukan error.

Jika ingin melihat log:

```bash
docker compose logs -f backend ai
```

Tekan `Ctrl+C` untuk keluar dari tampilan log; container tetap berjalan.

## Langkah 3 — Buat HiveMQ Cloud Serverless gratis

Pada antarmuka HiveMQ terbaru, istilah **cluster** sudah diganti menjadi **broker**.
Keduanya berarti layanan MQTT Cloud yang akan menerima data dari ESP32.

1. Buka <https://app.hivemq.com/> dan buat akun/login.
2. Pada menu hitam bagian atas, klik **Connect** di sebelah kanan **Explore**.
3. Klik **Get Broker or Edge**.
4. Pada pertanyaan **How do you want to get started?**, pilih
   **Deploy a new Broker**.
5. Pada **Choose how to run HiveMQ**, pilih **HiveMQ Cloud**, lalu klik **Continue**.
6. Pada **Select your Cloud Plan**, pilih **Serverless**. Jangan pilih Starter karena
   proyek ini cukup memakai paket Serverless gratis.
7. Klik **Start Free Trial**. Untuk Serverless, broker gratis langsung dibuat di AWS.
8. Tunggu broker muncul pada halaman **Connect** dan statusnya siap/running.
9. Klik broker tersebut, lalu klik **Configure**.
10. Salin hostname pada bagian connection details. Bentuknya mirip
    `xxxxxx.s1.eu.hivemq.cloud`. Jangan salin `mqtts://` dan jangan tambahkan `:8883`.
11. Masih pada halaman Configure, buka tab **Access Management**.
12. Pada bagian **Authentication → Credentials**, klik **Add New**.

Buat tiga credential berikut. Pada paket Serverless saat ini, permission dipilih pada
level credential dan tidak menyediakan filter topic khusus pada form ini. Gunakan
password berbeda dan hanya karakter huruf, angka, titik, garis bawah, atau tanda minus
agar aman dibaca file `.env`.

### Credential A — backend

- Username: `reksa-backend`
- Permission Type: **Publish and Subscribe**

### Credential B — helmet

- Username: `reksa-helmet-w01`
- Permission Type: **Publish and Subscribe**

### Credential C — gateway

- Username: `reksa-gateway-01`
- Permission Type: **Publish and Subscribe**

Catat hostname, tiga username, dan tiga password pada password manager/kertas lokal.
Jangan kirim password ke chat dan jangan masukkan ke Git. Setelah membuat credential,
tunggu sekitar satu menit agar konfigurasi aktif.

**Berhasil jika:** satu broker muncul pada menu Connect dan tiga username tampil pada
daftar credential.

Dokumentasi resmi: [HiveMQ Cloud Quick Start](https://docs.hivemq.com/hivemq-cloud/quick-start-guide.html).

## Langkah 4 — Buat project Google Cloud dan aktifkan Firebase

Lakukan ini sekarang agar Project ID bisa langsung dimasukkan ke skrip konfigurasi.

1. Buka <https://console.cloud.google.com/projectcreate>.
2. Isi nama, misalnya `REKSA GEMASTIK 2026`.
3. Isi **Project ID** yang unik, misalnya `reksa-gemastik-wielio`. Project ID tidak
   dapat diganti setelah dibuat—catat persis hurufnya.
4. Klik **Create** dan pastikan project baru itu sedang terpilih.
5. Buka **Billing** dan hubungkan billing account. Cloud Run memerlukan billing aktif,
   walaupun pemakaian kecil masih dapat berada dalam free tier.
6. Buka <https://console.cloud.google.com/billing/budgets>, buat budget kecil dan
   aktifkan email alert 50%, 90%, dan 100%. Budget alert bukan pembatas biaya otomatis.
7. Buka <https://console.firebase.google.com/>, pilih **Add project**, lalu pilih project
   Google Cloud yang baru dibuat untuk menambahkan Firebase.
8. Google Analytics boleh dimatikan untuk demo ini.
9. Pada Firebase, buka **Build → Hosting → Get started**. Cukup lanjut sampai Hosting
   aktif; file lokal sudah tersedia sehingga tidak perlu menjalankan `firebase init`.

**Berhasil jika:** project yang sama terlihat pada Google Cloud dan Firebase, serta
menu Firebase Hosting sudah aktif.

## Langkah 5 — Pasang alat bantu lokal

Pada Fedora, jalankan:

```bash
sudo dnf install -y openssl mosquitto
openssl version
mosquitto_pub --help | head -n 1
```

**Berhasil jika:** versi OpenSSL muncul dan `mosquitto_pub` menampilkan bantuan.

## Langkah 6 — Buat seluruh file credential secara otomatis

Jalankan:

```bash
cd '/home/wielio/Documents/Wiefran/Proyek/REKSA/REKSA'
./deploy/setup-hivemq.sh
```

Skrip akan menanyakan data satu per satu. Saat password diketik, layar memang tidak
menampilkan karakter apa pun; ketik lalu tekan `Enter`. Untuk Google Project ID,
masukkan ID dari Langkah 4, bukan nama project.

Skrip otomatis:

- membuat `.env.hivemq` untuk backend;
- membuat `bridge/.env` untuk gateway;
- membuat `arduino/helm_v1/secrets.h` untuk ESP32;
- mengambil rantai sertifikat TLS dari endpoint HiveMQ;
- memberi izin file `600` dan memastikan file rahasia diabaikan Git.

Cek tanpa memperlihatkan isi password:

```bash
ls -l .env.hivemq bridge/.env arduino/helm_v1/secrets.h
git status --short --ignored | grep -E '(\.env\.hivemq|bridge/\.env|secrets\.h)'
```

**Berhasil jika:** ketiga file ada, permission diawali `-rw-------`, dan status Git
menunjukkan file tersebut sebagai ignored (`!!`).

## Langkah 7 — Uji HiveMQ TLS, publish, subscribe, dan QoS 1

Jalankan satu perintah:

```bash
./deploy/test-hivemq.sh
```

**Berhasil jika:** muncul:

```text
BERHASIL: koneksi TLS, publish, subscribe, dan QoS 1 HiveMQ berfungsi.
```

Jika muncul `not authorised`, perbaiki Permission Type credential backend menjadi
Publish and Subscribe. Jika timeout, periksa hostname/port 8883 dan
tunggu satu menit setelah pembuatan credential.

## Langkah 8 — Jalankan backend lokal memakai HiveMQ Cloud

Hentikan stack biasa, kemudian start dengan override HiveMQ:

```bash
docker compose down
docker compose --env-file .env.hivemq \
  -f docker-compose.yml \
  -f docker-compose.hivemq.yml \
  up --build -d
docker compose --env-file .env.hivemq \
  -f docker-compose.yml \
  -f docker-compose.hivemq.yml \
  ps
docker compose --env-file .env.hivemq \
  -f docker-compose.yml \
  -f docker-compose.hivemq.yml \
  logs --tail=100 backend
```

**Berhasil jika:** backend sehat dan log tidak berisi `Not authorized`, `TLS`, atau
`connection refused`. Mosquitto lokal masih dapat terlihat karena merupakan bagian
stack dasar, tetapi backend sudah diarahkan ke hostname HiveMQ melalui override.

Dashboard tetap dibuka dari <http://localhost:5173>.

## Langkah 9 — Upload firmware ke ESP32

Cara paling aman untuk pertama kali adalah Arduino IDE:

1. Buka `arduino/helm_v1/helm_v1.ino`.
2. Pada Boards Manager, pasang board package **esp32 by Espressif Systems**.
3. Pada Library Manager, pasang **PubSubClient**, **ArduinoJson**, **DHT sensor
   library**, dan **NimBLE-Arduino by h2zero**. NimBLE diperlukan agar scanner BLE
   dan TLS HiveMQ muat bersamaan pada RAM ESP32 tanpa PSRAM.
4. Pilih board ESP32 milikmu dan port USB yang benar.
5. Klik **Verify**. Jika berhasil, klik **Upload**.
6. Buka Serial Monitor dengan baud rate yang sama dengan `Serial.begin(...)` di
   firmware (umumnya `115200`).

**Berhasil jika:** Serial Monitor memperlihatkan Wi-Fi tersambung, MQTT TLS tersambung,
dan payload telemetry dikirim/di-ACK. Jika compile gagal, kirim seluruh error mulai
dari baris pertama `error:`.

## Langkah 10 — Buktikan offline-first dan retransmission

1. Biarkan ESP32 online sampai ada pesan `Telemetry diterima`/ACK.
2. Rekam Serial Monitor atau simpan log ke `evidence/serial-run-01.log`.
3. Matikan hotspot/router selama 20 detik.
4. Selama offline, gerakkan helmet atau jalankan skenario sensor.
5. Pastikan alarm lokal tetap bereaksi dan counter buffer bertambah.
6. Nyalakan koneksi kembali.
7. Pastikan message ID lama dikirim lagi dengan `attempt > 1`, lalu menerima ACK.

Analisis log:

```bash
mkdir -p evidence
python tools/analyze_firmware_metrics.py evidence/serial-run-01.log
```

**Berhasil jika:** reconnect terjadi, pesan tertunda terkirim ulang, ACK bertambah,
dan `dropped=0`. Jangan mengklaim *zero data loss* bila ada pengujian dengan
`dropped > 0`.

## Langkah 11 — Instal Google Cloud CLI pada Fedora

Salin blok berikut:

```bash
sudo tee /etc/yum.repos.d/google-cloud-sdk.repo >/dev/null <<'EOF'
[google-cloud-cli]
name=Google Cloud CLI
baseurl=https://packages.cloud.google.com/yum/repos/cloud-sdk-el9-x86_64
enabled=1
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg
EOF
sudo dnf install -y libxcrypt-compat google-cloud-cli
gcloud version
node --version
npx --yes firebase-tools@latest --version
```

Firebase CLI memerlukan Node.js 18 atau lebih baru. Jika `node --version` lebih rendah,
jangan deploy dahulu; perbarui Node.js.

Dokumentasi resmi: [instalasi Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/install-sdk)
dan [Firebase CLI](https://firebase.google.com/docs/cli).

## Langkah 12 — Login ke Google Cloud dan Firebase

Jalankan satu per satu dan selesaikan login pada browser:

```bash
gcloud auth login
gcloud auth application-default login
npx --yes firebase-tools@latest login
gcloud auth list
npx --yes firebase-tools@latest projects:list
```

**Berhasil jika:** emailmu berstatus `ACTIVE` pada `gcloud auth list`, dan Project ID
REKSA terlihat pada daftar Firebase.

## Langkah 13 — Preflight sebelum memakai cloud

Jalankan build lokal penuh:

```bash
cd '/home/wielio/Documents/Wiefran/Proyek/REKSA/REKSA'
./deploy/gcp/preflight.sh
```

**Berhasil jika:** baris terakhir berbunyi `Local build preflight passed`.

## Langkah 14 — Deploy AI, backend, Pub/Sub, Firestore, dan dashboard

Jalankan:

```bash
cd '/home/wielio/Documents/Wiefran/Proyek/REKSA/REKSA'
./deploy/gcp/deploy.sh
```

Masukkan Project ID saat diminta. Skrip meminta Project ID sekali lagi sebagai
pengaman agar tidak men-deploy ke project yang salah. Proses build pertama dapat
memakan beberapa menit.

Skrip akan otomatis:

1. mengaktifkan API Cloud Run, Cloud Build, Artifact Registry, Pub/Sub, Firestore;
2. membuat service account dengan fungsi terpisah;
3. membuat topic `reksa-telemetry` dan push subscription;
4. deploy AI dan backend stateless ke Cloud Run;
5. membuat Firestore untuk arsip envelope;
6. build frontend dengan URL backend hasil deploy;
7. deploy frontend ke Firebase Hosting.

**Berhasil jika:** terminal menampilkan `REKSA deployment complete` beserta tiga URL:
Dashboard, Backend, dan AI. Salin tiga URL tersebut ke catatan.

Uji URL dengan mengganti nilai sesuai output deploy:

```bash
read -r -p 'Tempel Backend URL: ' BACKEND_URL
read -r -p 'Tempel AI URL: ' AI_URL
curl -fsS "${BACKEND_URL}/api/v1/health"
curl -fsS "${AI_URL}/health"
```

## Langkah 15 — Buat key gateway dan jalankan bridge

Set Project ID pada terminal:

```bash
read -r -p 'Google Cloud Project ID: ' GCP_PROJECT_ID
export GCP_PROJECT_ID
sed -i "s/^GOOGLE_CLOUD_PROJECT=.*/GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID}/" bridge/.env
grep '^GOOGLE_CLOUD_PROJECT=' bridge/.env
```

Buat service-account key khusus gateway. File ini rahasia dan sudah diabaikan Git:

```bash
mkdir -p secrets
gcloud iam service-accounts keys create secrets/gcp-service-account.json \
  --iam-account="reksa-bridge@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
chmod 600 secrets/gcp-service-account.json
docker compose -f docker-compose.bridge.yml up --build -d
docker compose -f docker-compose.bridge.yml logs -f bridge
```

**Berhasil jika:** log menampilkan `Connected to HiveMQ and subscribed` dan tidak
menampilkan error Google credential/Pub/Sub. Tekan `Ctrl+C` untuk keluar dari log.

Key JSON dipakai hanya pada gateway/laptop demo. Setelah lomba, hapus key dari IAM
Google Cloud dan buat key baru bila diperlukan; jangan pernah upload JSON ke Git.

## Langkah 16 — Uji alur ujung-ke-ujung

Dengan ESP32 menyala, buka dashboard Firebase dari output deploy. Lalu pantau:

```bash
gcloud run services logs read reksa-backend \
  --region asia-southeast2 \
  --limit 100
docker compose -f docker-compose.bridge.yml logs --tail=100 bridge
```

**Berhasil jika:**

- ESP32 mengirim message ID dan mendapat ACK;
- bridge mencatat `Buffered ...` lalu `Forwarded ... to Pub/Sub`;
- backend Cloud Run menerima push tanpa error;
- data pekerja/peringatan tampil pada dashboard Firebase;
- ketika internet gateway diputus, data menetap di outbox dan diteruskan setelah
  koneksi pulih.

## Langkah 17 — Pemeriksaan keamanan terakhir

Jalankan sebelum commit atau mengirim ZIP:

```bash
git status --short --ignored | grep -E '(\.env|secrets\.h|service-account\.json)'
git ls-files | grep -E '(\.env\.hivemq|bridge/\.env|secrets\.h|service-account\.json)' || true
```

**Berhasil jika:** file rahasia hanya muncul dengan tanda ignored (`!!`) dan perintah
`git ls-files` tidak mencetak file rahasia.

## Perintah harian setelah semuanya sudah pernah berhasil

Menyalakan aplikasi lokal + HiveMQ:

```bash
cd '/home/wielio/Documents/Wiefran/Proyek/REKSA/REKSA'
docker compose --env-file .env.hivemq \
  -f docker-compose.yml \
  -f docker-compose.hivemq.yml \
  up -d
docker compose -f docker-compose.bridge.yml up -d
```

Mematikan container lokal tanpa menghapus data:

```bash
docker compose --env-file .env.hivemq \
  -f docker-compose.yml \
  -f docker-compose.hivemq.yml \
  down
docker compose -f docker-compose.bridge.yml down
```

Jangan tambahkan opsi `-v` ketika mematikan jika tidak ingin volume/data lokal ikut
terhapus.
