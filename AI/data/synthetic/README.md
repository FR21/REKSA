# REKSA Synthetic AI Datasets

Folder ini berisi data sintetis untuk menguji pipeline training sebelum data purwarupa asli tersedia.

## File

- `forecasting_windows_synthetic.csv`: 15.000 temporal windows untuk Near-Miss Risk Forecaster.
- `event_dataset_synthetic.csv`: 6.000 candidate events untuk AI Priority Engine.
- `synthetic_dataset_report.json`: distribusi kelas, skenario, grup, dan hasil pemeriksaan konsistensi.

Semua record memiliki `data_origin=SYNTHETIC`. Tidak ada record yang diberi label `VERIFIED_NEAR_MISS`.

## Skenario

Data dibentuk dari kombinasi skenario berikut:

```text
NORMAL_PASSAGE
NORMAL_WORK_NEAR_MACHINE
RSSI_FLUCTUATION
FORKLIFT_APPROACH
FORKLIFT_CROSSING
PROLONGED_DANGER
SUDDEN_MOTION_AFTER_WARNING
IMPACT_CANDIDATE
FALL_CANDIDATE
REPEATED_EXPOSURE
HAZARD_INACTIVE
BLE_PACKET_LOSS
AIR_QUALITY_DEGRADATION
```

Nilai sensor diberi variasi antar-peserta, antar-sesi, dan random noise. Label juga probabilistik sehingga dua event dengan skenario sama tidak selalu memperoleh target yang sama.

## Target Forecaster

```text
escalated_within_horizon = 0 atau 1
```

Kolom input model ditentukan oleh `FORECAST_FEATURES` di `src/reksa_ai/features.py`. Jangan memasukkan kolom identitas, waktu, `scenario_id`, `target_source`, atau `data_origin` sebagai fitur.

## Target Priority Engine

```text
supervisor_priority = LOW, MEDIUM, atau HIGH
```

Nilai tersebut adalah **synthetic supervisor-like priority**, bukan keputusan supervisor sebenarnya. Kolom `verification_label`, `scenario_id`, `label_source`, dan `data_origin` adalah metadata evaluasi dan tidak boleh menjadi input model.

## Generate ulang

```bash
cd AI
PYTHONPATH=src python scripts/generate_synthetic_datasets.py \
  --output-dir data/synthetic \
  --forecast-rows 15000 \
  --priority-rows 6000 \
  --participants 40 \
  --sessions 12 \
  --seed 20260807
```

Seed yang sama menghasilkan isi dataset yang sama. Gunakan seed berbeda hanya untuk eksperimen tambahan, bukan untuk membuat train dan test yang sangat mirip. Split tetap harus berdasarkan participant/session, bukan mengacak baris.

## Penggunaan yang benar

Dataset ini cocok untuk:

- memeriksa data cleaning dan feature pipeline;
- memastikan model, API, dan dashboard tersambung;
- membandingkan rule baseline, Logistic Regression, dan Random Forest;
- menyiapkan notebook training awal.

Dataset ini tidak cukup untuk:

- mengklaim performa keselamatan di lingkungan nyata;
- menetapkan threshold produksi;
- mengaktifkan warning keselamatan secara otomatis;
- menggantikan controlled trajectories dan label supervisor dari purwarupa REKSA.

Setelah data nyata tersedia, pertahankan `data_origin` dan evaluasi pada peserta/sesi nyata yang tidak pernah masuk training.

