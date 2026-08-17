# Dataset REKSA AI

## 1. Raw sensor samples

Gunakan [raw_sensor_samples.csv](data/templates/raw_sensor_samples.csv) sebagai header logger. Satu baris adalah satu timestamp sensor, belum menjadi satu contoh training.

Kolom identitas yang tidak boleh hilang:

- `participant_id`: orang/dummy/rig yang menjalankan skenario.
- `session_id`: satu sesi pengambilan data.
- `scenario_id`: normal approach, crossing, controlled high risk, dan lain-lain.
- `trajectory_id`: satu rangkaian gerak kontinu.
- `event_id`: kosong di luar event; sama untuk seluruh sampel dalam satu event.

Kolom label:

- `forecast_target`: `1` jika outcome berisiko terjadi pada timestamp tersebut, selain itu `0`.
- `target_source`: `CONTROLLED_SCENARIO` atau `SUPERVISOR_VERIFIED`.
- `supervisor_priority`: `LOW`, `MEDIUM`, atau `HIGH`; target Priority Engine.
- `verification_label`: hasil pemeriksaan aktual, bukan output AI.

Nilai `supervisor_priority` harus mencerminkan urutan pemeriksaan yang dinilai supervisor. `verification_label` disimpan terpisah supaya model tidak menyamakan “prioritas tinggi” dengan “pasti near-miss”.

## 2. Forecasting windows

Gunakan [forecasting_windows.csv](data/templates/forecasting_windows.csv). Satu baris adalah fitur yang dihitung dari window temporal. Target `escalated_within_horizon` menyatakan apakah outcome muncul setelah window dan masih dalam horizon.

Simpan window negatif dari aktivitas normal, safe interaction, dan false alarm. Tanpa kelas negatif, forecaster tidak dapat belajar membedakan pola berisiko dari pekerjaan normal.

Overlapping window dari trajectory yang sama sangat berkorelasi. Karena itu seluruh window dari satu peserta/sesi wajib berada pada partition yang sama.

## 3. Event dataset

Gunakan [event_dataset.csv](data/templates/event_dataset.csv). Satu baris adalah satu candidate safety event lengkap. Fitur suhu, kelembapan, dan MQ135 adalah konteks; BLE, durasi, gerakan, impact/fall candidate, status hazard, dan paparan berulang adalah indikator utama.

Label verifikasi yang direkomendasikan:

```text
VERIFIED_NEAR_MISS
FALSE_ALARM
NORMAL_ACTIVITY
HAZARD_INACTIVE
IMPACT_OR_FALL_CANDIDATE
INSUFFICIENT_EVIDENCE
SIMULATED_HIGH_RISK
```

## Quality gate sebelum training

- Timestamp monoton di dalam setiap trajectory.
- Tidak ada duplikat `(trajectory_id, timestamp)`.
- Unit konsisten: RSSI dBm, acceleration g, gyroscope deg/s, suhu Celsius.
- Semua kelas muncul pada lebih dari satu peserta dan sesi.
- Tidak ada ID orang, sesi, atau skenario yang bocor sebagai fitur model.
- Jumlah kelas, missing value, dan distribusi fitur dicatat per versi dataset.
- Data simulasi tidak disebut sebagai verified real near-miss.

