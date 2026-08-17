# AI Data and Evidence Workflow

## Rekam data perangkat nyata

Publikasi dashboard 2,5 detik terlalu jarang untuk pola temporal. Untuk eksperimen AI,
gunakan sesi 5–10 Hz melalui topik khusus atau buffer lokal, lalu simpan identitas
peserta, sesi, skenario, dan trajectory.

Logger mendukung HiveMQ TLS:

```bash
cd AI
. .venv/bin/activate
export MQTT_PASSWORD='password-logger'
python scripts/log_mqtt.py \
  --host your-cluster.s1.eu.hivemq.cloud --port 8883 --tls \
  --username reksa-logger \
  --output data/raw/P01-S01.csv \
  --participant P01 --session S01 \
  --scenario NORMAL_APPROACH --trajectory TRJ-P01-S01-001
```

Lengkapi label setelah sesi. Skenario terkontrol harus memakai
`target_source=CONTROLLED_SCENARIO`, bukan `SUPERVISOR_VERIFIED`.

## Bangun dataset dan latih dua engine

```bash
python scripts/build_datasets.py data/raw/all-sessions.csv \
  --forecast-output data/processed/forecasting_windows.csv \
  --event-output data/processed/event_dataset.csv

python scripts/train_forecaster.py data/processed/forecasting_windows.csv \
  --output models/near_miss_forecaster.joblib --version forecaster-real-v1

python scripts/train_priority_engine.py data/processed/event_dataset.csv \
  --output models/priority_engine.joblib --version priority-real-v1

python scripts/compare_models.py \
  models/near_miss_forecaster.json models/priority_engine.json \
  --output models/model-evidence.md
```

Training memakai held-out group `participant_id + session_id`, membandingkan baseline
aturan, Logistic Regression, dan Random Forest. Artifact hanya direkomendasikan bila
F1 model terpilih mengungguli baseline. Forecaster juga mencatat recall, precision,
Brier score, ROC-AUC bila valid, confusion matrix, serta status calibration.

Dataset sintetis hanya menguji pipeline. `model-evidence.md` yang berasal dari dataset
sintetis tidak boleh digunakan sebagai klaim kinerja keselamatan dunia nyata.
