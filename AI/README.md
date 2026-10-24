# REKSA AI

Paket ini berisi tiga mesin analitik yang perannya terpisah dari sistem keselamatan lokal:

| Engine | Waktu bekerja | Input | Output | Deployment |
|---|---|---|---|---|
| Near-Miss Risk Forecaster | Sebelum/ketika pola berkembang | Window temporal BLE-RSSI + MPU6050 (10s) | Probabilitas eskalasi, risk level, faktor dominan | Cloud Run / Docker (Port 8100) |
| AI Priority Engine | Setelah event selesai | Baris event + label verifikasi supervisor | Prioritas pemeriksaan (LOW/MED/HIGH), skor | Cloud Run / Docker (Port 8100) |
| Operational Anomaly Detector | Berjalan bersama telemetri | 14 parameter telemetri sensor rutin | Decision score, deteksi anomali/outlier | Cloud Run / Docker (Port 8100) |

Ketiganya **tidak memverifikasi near-miss secara otomatis**, tidak mengganti state machine, dan tidak boleh menjadi satu-satunya pengendali buzzer atau vibration motor. Keputusan final tetap pada supervisor K3.

## Isi folder

```text
AI/
├── data/                       template dan dataset sintetis operasional
├── examples/                   contoh request API (forecast & priority)
├── models/                     artifact model terlatih (.joblib dan .json)
├── notebooks/                  notebook training terpadu (Reksa_AI_Training.ipynb)
├── src/reksa_ai/               source code FastAPI dan inference engine
└── tests/                      suite unit test (pytest)
```

## Menjalankan API sekarang

API menyajikan 3 engine inference (Near-Miss Risk Forecaster, Priority Engine, dan Operational Anomaly Detector) di port `8100`:

```bash
uvicorn reksa_ai.service:app --reload --port 8100
```

Buka dokumentasi interaktif Swagger di `http://localhost:8100/docs`.

Contoh inference:

```bash
curl -X POST http://localhost:8100/v1/forecast \
  -H 'Content-Type: application/json' \
  --data @examples/forecast_request.json

curl -X POST http://localhost:8100/v1/prioritize \
  -H 'Content-Type: application/json' \
  --data @examples/priority_request.json
```

## Dataset Operasional

Dataset sintetis operasional siap pakai berada di:

```text
data/synthetic/forecasting_windows_operational_synthetic.csv  # 15.000 window temporal
data/synthetic/event_dataset_operational_synthetic.csv        # 6.000 event insiden
data/synthetic/iot_telemetry_schema_synthetic.jsonl           # Skema telemetri IoT
```

Seluruh proses eksplorasi data, pipeline windowing, perbandingan model ML, kalibrasi probabilitas, dan ekspor model dijalankan terpusat di notebook:
`notebooks/Reksa_AI_Training.ipynb`.

## Training lokal atau Google Colab

Notebook lengkap untuk ketiga model AI tersedia di:

```text
notebooks/Reksa_AI_Training.ipynb
```

Notebook tersebut memperlihatkan seluruh proses secara eksplisit: import, cleaning, leakage audit, participant holdout, grouped cross-validation, preprocessing, baseline comparison, calibration, evaluasi, feature importance, artifact export, dan demonstrasi output JSON real-time.

Untuk memakainya:

```bash
export REKSA_FORECAST_MODEL=models/near_miss_forecaster.joblib
export REKSA_PRIORITY_MODEL=models/priority_engine.joblib
export REKSA_ANOMALY_MODEL=models/operational_anomaly_detector.joblib
uvicorn reksa_ai.service:app --host 0.0.0.0 --port 8100
```

## Deployment Cloud Run (CI/CD)

Layanan `reksa-ai` dapat dideploy ke Google Cloud Run baik secara otomatis melalui GitHub Actions (`.github/workflows/deploy-ai.yml`) maupun manual:

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

Spesifikasi hemat biaya:
- `--min-instances 0`: Scale-to-zero otomatis (biaya $0 / Rp 0 saat idle).
- `--cpu-throttling`: Alokasi CPU hanya aktif saat inferensi diproses.
- `--max-instances 1`: Menjaga batas biaya operasional cloud.

## Catatan sampling forecaster

`helm_v1.ino` saat ini publish setiap sekitar 2,5 detik. Window 10 detik hanya mempunyai sekitar empat sampel, yang terlalu kasar untuk menangkap bentuk gerakan secara baik. Untuk eksperimen forecaster, rekam BLE + MPU6050 pada 5-10 Hz melalui topik telemetry khusus atau buffer lokal. Jalur MQTT dashboard 2,5 detik dapat tetap dipertahankan agar tidak membanjiri backend.

Model forecaster sebaiknya dijalankan di backend lebih dahulu. Pemindahan ke ESP32 baru dilakukan setelah model terbukti lebih baik dari threshold baseline, ukuran flash/RAM cukup, waktu inference terukur, dan state machine lokal tetap memiliki prioritas tertinggi.

## Tampilan supervisor

Dashboard Web REKSA menampilkan:

- `Live Monitoring`: probabilitas eskalasi forecaster, sumber inference, dan faktor dominan. Tulis “baseline score” apabila `probability_is_calibrated=false`.
- `Event Review Queue`: urutkan event berdasarkan `priority_score`, tampilkan reason codes dan penjelasan.
- `Event Detail`: tombol verifikasi terpisah untuk `VERIFIED_NEAR_MISS`, `FALSE_ALARM`, `NORMAL_ACTIVITY`, `HAZARD_INACTIVE`, `IMPACT_OR_FALL_CANDIDATE`, dan `INSUFFICIENT_EVIDENCE`.
- Riwayat model: selalu tampilkan `model_version` dan `generated_at` agar hasil dapat diaudit.

Backend utama dapat memanggil `/v1/forecast` saat window tersedia dan `/v1/prioritize` ketika event ditutup. Hasil kemudian disimpan bersama event dan dikirim ke React melalui WebSocket. Jangan memanggil API AI langsung dari browser produksi karena validasi, autentikasi, audit, dan fallback sebaiknya dikelola backend REKSA.

Reason codes versi awal menggunakan perbandingan fitur dengan threshold yang mudah diaudit dan ditandai `explanation_method=THRESHOLD_REASON_CODES`. Kode ini menjelaskan indikator pada event, bukan klaim SHAP atau kontribusi kausal dari model.

## Batas ilmiah

- Template CSV hanyalah definisi struktur, bukan data training yang sah.
- Dataset harus memiliki contoh positif dan negatif.
- Controlled scenario dan verified real event harus dapat dibedakan lewat `target_source`.
- Model tidak boleh dilatih otomatis setiap kali supervisor memberi satu label. Data baru masuk batch training versi berikutnya dan hanya dideploy setelah evaluasi.
- Akurasi tinggi pada sesi yang sudah pernah dilihat bukan bukti generalisasi. Uji peserta, sesi, dan hari yang sepenuhnya tidak masuk training.
