# Demo REKSA — Kurang dari 3 Menit

1. Buka Overview dan tunjukkan KPI, status perangkat, worker risk, dan trend near-miss.
2. Buka Settings → IoT Device Registry untuk memastikan helm pekerja dan hazard node sudah terdaftar.
3. Jalankan helm ESP32 atau publish payload MQTT contoh dari `docs/mqtt-topics.md`.
4. Buka Live Monitoring. Amati worker berubah otomatis tanpa refresh manual.
5. Tekan **Test Helm MQTT** untuk mengirim command warning ke topic helm.
6. Klik pekerja untuk meninjau risk factor, environment, impact, air quality, dan near-miss history.

Gunakan **Reset Demo Data** di Settings untuk mengembalikan seed worker, hazard, dan device bawaan.
