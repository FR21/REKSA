# Strategi Teknis REKSA untuk GEMASTIK XIX

## Keputusan produk

Fitur unggulan REKSA adalah **AI Early-Warning Unsafe Approach**: piranti memanfaatkan
window temporal BLE RSSI dan MPU6050 untuk memberi advisory 3-5 detik sebelum pola
pendekatan menjadi kritis. State machine lokal tetap mengaktifkan vibration/buzzer
berdasarkan ambang K3 sehingga keselamatan tidak bergantung pada internet atau AI.

Cloud adalah penguat keterhubungan dan audit, bukan pusat keselamatan:

```text
ESP32 safety rule + TinyML candidate
        -> MQTT QoS 1/TLS
        -> HiveMQ Cloud
        -> FastAPI -> REKSA AI advisory -> PostgreSQL
        -> WebSocket -> supervisor dashboard
```

## Pemetaan langsung ke penilaian final

1. **Kecerdasan piranti (20%)**: temporal feature engineering, perbandingan baseline,
   Logistic Regression, dan Random Forest; inference source serta versi model terlihat.
2. **Kompleksitas, problem solving, dan fungsionalitas (20%)**: early warning,
   local fail-safe, near-miss audit, dan supervisor acknowledgement bekerja end-to-end.
3. **Desain/model dan implementasi (20%)**: helm, hazard beacon, MQTT, backend, AI,
   database, dan dashboard menjadi satu alur yang dapat didemonstrasikan.
4. **Efektivitas, efisiensi, biaya, dan adaptabilitas (20%)**: ukur recall, F1,
   false alarm/jam, end-to-end latency, RAM, flash, konsumsi daya, dan mode offline.
5. **Presentasi dan demo (20%)**: tampilkan pendekatan aman, pendekatan berbahaya,
   early warning, acknowledgement, lalu cabut internet untuk membuktikan fail-safe.

## Definition of done

- Dashboard tidak memuat angka probabilitas atau nama model hard-coded.
- Tanpa artifact terlatih, UI menyebut `RULE_BASED_BASELINE` dan skor belum terkalibrasi.
- Artifact hanya dideploy jika mengalahkan baseline pada participant/session holdout.
- Data sintetis hanya menguji pipeline dan tidak diklaim sebagai performa lapangan.
- Telemetry eksperimen direkam 5-10 Hz dengan peserta, sesi, dan hari yang terpisah.
- MQTT cloud menggunakan TLS, kredensial per device, ACL topic, QoS 1, dan LWT.
- Helm tetap memberi warning ketika broker, backend, AI, atau internet terputus.

## Urutan kerja paling efisien

1. Integrasi baseline end-to-end dan demo MQTT fisik.
2. Rekam controlled scenario positif/negatif pada 5-10 Hz.
3. Train dan evaluasi tiga kandidat; dokumentasikan confusion matrix dan false alarm.
4. Deploy model pemenang ke backend dalam shadow mode.
5. Ekspor kandidat kecil ke ESP32 setelah benchmark RAM, flash, dan latency.
6. Migrasikan broker ke HiveMQ Cloud dan database ke PostgreSQL terkelola.
7. Rekam video demo menggunakan empat skenario yang sama dengan tabel hasil uji.

Jangan menambah A*, computer vision, LLM, atau banyak model lain sebelum alur di atas
selesai dan terukur. Satu AI yang relevan dan dapat dipertanggungjawabkan lebih kuat
daripada banyak label teknologi yang tidak terintegrasi.
