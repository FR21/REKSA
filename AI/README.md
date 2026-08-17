# REKSA AI

Paket ini berisi dua mesin analitik yang perannya terpisah dari sistem keselamatan lokal:

| Engine | Waktu bekerja | Input | Output | Deployment awal |
|---|---|---|---|---|
| Near-Miss Risk Forecaster | Sebelum/ketika pola berkembang | Window temporal BLE-RSSI + MPU6050 | Probabilitas eskalasi dan level advisory | Backend lebih dahulu; ESP32 hanya setelah lolos benchmark ukuran/latensi |
| AI Priority Engine | Setelah event selesai | Satu baris per event + label supervisor | Prioritas pemeriksaan, skor, dan alasan | Backend/dashboard |

Keduanya **tidak memverifikasi near-miss**, tidak mengganti state machine, dan tidak boleh menjadi satu-satunya pengendali buzzer atau vibration motor. Keputusan final tetap pada supervisor K3.

## Isi folder

```text
AI/
├── data/templates/             template data mentah, forecasting window, dan event
├── examples/                   contoh request API
├── integration/                kontrak TypeScript untuk dashboard
├── models/                     artifact model hasil training (tidak masuk Git)
├── scripts/
│   ├── log_mqtt.py             logger MQTT ke CSV
│   ├── build_datasets.py       raw samples -> dua dataset
│   ├── train_forecaster.py
│   └── train_priority_engine.py
├── src/reksa_ai/
│   ├── contracts.py            validasi input/output
│   ├── features.py             feature engineering temporal
│   ├── datasets.py             windowing dan event aggregation
│   ├── baselines.py            baseline transparan untuk cold start
│   ├── training.py             Logistic Regression vs Random Forest
│   ├── inference.py            pemuatan model dan fallback
│   └── service.py              API FastAPI
└── tests/
```

## Menjalankan API sekarang

API tetap dapat dicoba sebelum training. Dalam kondisi itu respons menyebut `RULE_BASED_BASELINE` dan `probability_is_calibrated=false`.

```bash
cd AI
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn reksa_ai.service:app --reload --port 8100
```

Buka dokumentasi interaktif di `http://localhost:8100/docs`.

Contoh inference:

```bash
curl -X POST http://localhost:8100/v1/forecast \
  -H 'Content-Type: application/json' \
  --data @examples/forecast_request.json

curl -X POST http://localhost:8100/v1/prioritize \
  -H 'Content-Type: application/json' \
  --data @examples/priority_request.json
```

## Jalur data

Untuk mencoba training sebelum data perangkat tersedia, dataset sintetis siap pakai berada di:

```text
data/synthetic/forecasting_windows_synthetic.csv  # 15.000 window
data/synthetic/event_dataset_synthetic.csv        # 6.000 event
data/synthetic/synthetic_dataset_report.json      # distribusi dan quality checks
```

Baca `data/synthetic/README.md` sebelum menggunakannya. Semua record ditandai `data_origin=SYNTHETIC`; dataset ini hanya untuk pengembangan pipeline dan tidak dapat menjadi bukti performa keselamatan nyata.

1. Rekam payload helmet:

```bash
python scripts/log_mqtt.py \
  --host localhost \
  --output data/raw/session-P01-S01.csv \
  --participant P01 \
  --session S01 \
  --scenario NORMAL_APPROACH \
  --trajectory TRJ-P01-S01-001
```

2. Setelah sesi, lengkapi `event_id`, `forecast_target`, `target_source`, `supervisor_priority`, dan `verification_label`. Jangan mengisi controlled scenario sebagai `VERIFIED_NEAR_MISS`; gunakan `target_source=CONTROLLED_SCENARIO` dan label seperti `SIMULATED_HIGH_RISK`.

3. Bentuk dua dataset:

```bash
python scripts/build_datasets.py data/raw/all-sessions.csv \
  --forecast-output data/processed/forecasting_windows.csv \
  --event-output data/processed/event_dataset.csv \
  --window-seconds 10 \
  --horizon-seconds 5 \
  --step-seconds 1
```

Window hanya memakai data sampai `window_ended_at`. Target dicari setelah titik itu dalam horizon prediksi, sehingga fitur tidak melihat masa depan.

## Training lokal atau Google Colab

Notebook lengkap untuk kedua AI tersedia di:

```text
notebooks/REKSA_AI_Training_Complete.ipynb
```

Notebook tersebut memperlihatkan seluruh proses secara eksplisit: import, cleaning, leakage audit, participant holdout, grouped cross-validation, preprocessing, baseline comparison, calibration, evaluasi, feature importance, artifact export, dan inference example.

Unggah folder `AI` dan dataset ke Colab, lalu jalankan:

```bash
pip install -e './AI[dev]'
cd AI
python scripts/train_forecaster.py data/processed/forecasting_windows.csv \
  --output models/near_miss_forecaster.joblib \
  --version forecaster-v1

python scripts/train_priority_engine.py data/processed/event_dataset.csv \
  --output models/priority_engine.joblib \
  --version priority-v1
```

Training membandingkan rule-based baseline, Logistic Regression, dan Random Forest, lalu memilih F1 terbaik di antara model ML. Split dilakukan per gabungan `participant_id + session_id`; satu grup tidak dapat muncul di train dan test. Forecaster mencoba kalibrasi sigmoid dengan group cross-validation dan akan menandai artifact sebagai tidak terkalibrasi jika grup/kelas belum cukup.

Artifact `.joblib` berisi model final. File `.json` di sampingnya berisi versi, jumlah data, policy split, confusion matrix, precision, recall, F1, ROC-AUC/Brier untuk forecaster, dan hasil semua model pembanding. Artifact hanya dilayani API jika `deployment_recommended=true`, yaitu skor F1 test model terpilih melampaui rule baseline; jika tidak, service kembali ke baseline dan melaporkan alasannya pada `/health`.

Untuk memakainya:

```bash
export REKSA_FORECAST_MODEL=models/near_miss_forecaster.joblib
export REKSA_PRIORITY_MODEL=models/priority_engine.joblib
uvicorn reksa_ai.service:app --host 0.0.0.0 --port 8100
```

## Catatan sampling forecaster

`helm_v1.ino` saat ini publish setiap sekitar 2,5 detik. Window 10 detik hanya mempunyai sekitar empat sampel, yang terlalu kasar untuk menangkap bentuk gerakan secara baik. Untuk eksperimen forecaster, rekam BLE + MPU6050 pada 5–10 Hz melalui topik telemetry khusus atau buffer lokal. Jalur MQTT dashboard 2,5 detik dapat tetap dipertahankan agar tidak membanjiri backend.

Model forecaster sebaiknya dijalankan di backend lebih dahulu. Pemindahan ke ESP32 baru dilakukan setelah model terbukti lebih baik dari threshold baseline, ukuran flash/RAM cukup, waktu inference terukur, dan state machine lokal tetap memiliki prioritas tertinggi.

## Tampilan supervisor

Kontrak frontend tersedia di [supervisor-ai.types.ts](integration/supervisor-ai.types.ts). Dashboard sebaiknya menampilkan:

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
