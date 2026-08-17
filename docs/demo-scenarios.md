# Demo REKSA — Kurang dari 3 Menit

1. Buka Overview dan tunjukkan KPI, status perangkat, worker risk, dan trend near-miss.
2. Buka Settings → IoT Device Registry untuk memastikan helm pekerja dan hazard node sudah terdaftar.
3. Jalankan helm ESP32 atau publish payload MQTT contoh dari `docs/mqtt-topics.md`.
4. Buka Live Monitoring. Amati worker berubah otomatis tanpa refresh manual.
5. Tekan **Test Helm MQTT** untuk mengirim command warning ke topic helm.
6. Klik pekerja untuk meninjau risk factor, environment, impact, air quality, dan near-miss history.

## Demo unggulan GEMASTIK

1. Tunjukkan status `AWAITING LIVE TELEMETRY`; jelaskan bahwa UI tidak memakai angka AI palsu.
2. Jalankan helm dan hazard F01. Setelah minimal dua telemetry, buka detail W01.
3. Dekatkan helm bertahap sehingga RSSI meningkat. Tunjukkan skor advisory, reason codes,
   inference source, model version, dan status kalibrasi.
4. Tunjukkan bahwa vibration/buzzer safety rule tetap bekerja tanpa menunggu AI.
5. Putuskan internet/broker. Helm harus tetap memperingatkan; dashboard menandai layanan
   atau perangkat tidak tersedia tanpa mengubahnya menjadi status aman.
6. Sambungkan kembali dan acknowledge event sebagai supervisor.

Saat model belum dilatih dengan data fisik, sebut hasil sebagai **baseline score**, bukan
probabilitas insiden. Data sintetis hanya membuktikan pipeline training dapat dijalankan.

Gunakan **Reset Demo Data** di Settings untuk mengembalikan seed worker, hazard, dan device bawaan.
