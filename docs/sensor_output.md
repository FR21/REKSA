# Spesifikasi Hardware, Telemetri, & Threshold IoT Helm REKSA

Dokumentasi teknis piranti keras (*hardware*), pinout ESP32, log serial debugging, skema payload telemetri MQTT, dan nilai ambang batas (*threshold*) keselamatan kerja pada node helm REKSA (`arduino/helm_v1/helm_v1.ino`).

---

## 1. Spesifikasi Hardware & Pinout ESP32

Mikrokontroler yang digunakan adalah **ESP32** (Xtensa dual-core 32-bit).

| Modul / Sensor | Antarmuka / GPIO ESP32 | Data yang Diambil | Rentang & Satuan | Frekuensi Sampling |
| :--- | :--- | :--- | :--- | :--- |
| **MPU-6050** (6-DOF IMU) | I2C (SDA: 21, SCL: 22) | Akselerasi 3-sumbu ($a_x, a_y, a_z$), giroskop ($g_x, g_y, g_z$), orientasi (*pitch, roll*), total $g$, deteksi benturan & jatuh bebas | $\pm 8g$ ($\text{m/s}^2$)<br>$\pm 500^\circ/\text{s}$ ($\text{deg/s}$)<br>Satuan $g$ ($1g \approx 9.80665 \text{ m/s}^2$) | 250 ms (4 Hz) |
| **DHT22** (AM2302) | 1-Wire Digital (GPIO 18) | Suhu ($T$) dan Kelembapan Relatif ($RH$) | $-40 \dots 80^\circ\text{C}$ ($\pm 0.5^\circ\text{C}$)<br>$0 \dots 100\%$ ($\pm 2\%$) | 2500 ms (2.5 detik) |
| **MQ-135** | ADC Analog (GPIO 34) | Kualitas udara / konsentrasi gas berbahaya | $0 - 4095$ (ADC 12-bit raw) | 250 ms |
| **NimBLE Scanner** | On-chip 2.4 GHz BLE | Beacon bahaya mesin (Mobile & Stationary), RSSI mentah & *smoothed* | $-30 \dots -100\text{ dBm}$ | Scan window 1 detik |
| **INMP441** | I2S Digital (WS: 32, SCK: 33, SD: 35) | Audio suara saat tombol PTT ditekan | Raw PCM 16-bit Mono 8 kHz | Saat tombol PTT aktif |
| **Tombol Kontrol** | Digital Input Interrupt | GPIO 25: Power/Standby Helm<br>GPIO 26: Push-To-Talk (PTT) | Active-Low (Debounced) | Event-driven |
| **Aktuator Alarm** | Digital Output | GPIO 19: Buzzer Aktif<br>GPIO 23: Vibration Motor<br>GPIO 2: LED Status Sistem<br>GPIO 4: LED Indikator PTT | Active-Low (Buzzer)<br>Active-High (Vibration) | Response < 20 ms |

---

## 2. Serial Monitor Debugging

Baud rate: `115200`.

### A. Status Booting & Konektivitas
```text
Memulai REKSA Smart Helmet Node...
Buzzer dikonfigurasi pada GPIO 19
Vibration dikonfigurasi pada GPIO 23
DHT22 dikonfigurasi pada GPIO 18
BLE Scanner aktif
Menghubungkan ke WiFi: REKSA_AP
WiFi terhubung! IP: 192.168.1.50
Waktu UTC tersinkron: 2026-10-14T13:30:00Z
Menghubungkan ke Broker MQTT...Terhubung!
Subscribed ke topic: REKSA/helmet/W01/warning
Subscribed ke topic: REKSA/helmet/W01/telemetry/ack
```

Kode status koneksi `PubSubClient` jika terjadi kegagalan:
- `0`: `MQTT_CONNECTED`
- `-1`: `MQTT_DISCONNECTED`
- `-2`: `MQTT_CONNECT_FAILED`
- `-3`: `MQTT_CONNECTION_LOST`
- `-4`: `MQTT_CONNECTION_TIMEOUT`

### B. Status Deteksi Hazard & Warning
```text
========== DAFTAR HAZARD ==========
Nama         : RK_M_FLK01
MAC          : aa:bb:cc:dd:ee:ff
RSSI mentah  : -61 dBm
RSSI rata2   : -63 dBm
Zona         : HIGH
-----------------------------------
HAZARD PRIORITAS: RK_M_FLK01 | RSSI: -63 dBm | Zona: HIGH
METRIC,ALARM_APPLIED,3,142850,wifi=1,mqtt=1
```

---

## 3. Format Telemetri MQTT

- **Topik Publish Sensor:** `REKSA/helmet/{WORKER_ID}/sensor` (contoh: `REKSA/helmet/W01/sensor`)
- **Interval Publish:** Setiap `2500 ms`
- **Mekanisme Outbox/Buffer:** Helm menyimpan hingga 12 payload di RAM jika koneksi terputus dan melakukan retransmisi berkala hingga menerima ACK pada topik `REKSA/helmet/{WORKER_ID}/telemetry/ack`.

### A. Payload dengan Hazard Aktif (Forklift Mendekat)
```json
{
  "message_id": "HELMET-W01-382a9f-142850",
  "device_id": "HELMET-W01",
  "worker_id": "W01",
  "timestamp": "2026-10-14T13:30:15Z",
  "acceleration": {
    "x": 0.15,
    "y": 0.08,
    "z": 9.82
  },
  "gyroscope": {
    "x": 1.2,
    "y": -0.5,
    "z": 0.3
  },
  "orientation": {
    "pitch": 0.8,
    "roll": -0.5,
    "yaw": 0.0
  },
  "impact_detected": false,
  "fall_detected": false,
  "impact_g": 1.01,
  "temperature": 29.4,
  "humidity": 68.2,
  "air_quality": {
    "mq135_raw": 840,
    "air_quality_level": "NORMAL",
    "gas_alert": false
  },
  "firmware_version": "0.2.0",
  "closest_hazard": {
    "hazard_id": "M-FLK-01",
    "hazard_type": "FORKLIFT",
    "hazard_category": "MOBILE",
    "operating_status": "ACTIVE",
    "rssi": -63,
    "proximity_level": "HIGH"
  }
}
```

### B. Payload Tanpa Hazard (Kondisi Normal)
Jika tidak ada beacon bahaya dalam jangkauan BLE, `closest_hazard` bernilai `null`:
```json
{
  "message_id": "HELMET-W01-382a9f-142855",
  "device_id": "HELMET-W01",
  "worker_id": "W01",
  "timestamp": "2026-10-14T13:30:18Z",
  "acceleration": {
    "x": 0.02,
    "y": 0.01,
    "z": 9.80
  },
  "gyroscope": {
    "x": 0.0,
    "y": 0.0,
    "z": 0.0
  },
  "orientation": {
    "pitch": 0.1,
    "roll": 0.0,
    "yaw": 0.0
  },
  "impact_detected": false,
  "fall_detected": false,
  "impact_g": 1.00,
  "temperature": 28.5,
  "humidity": 65.0,
  "air_quality": {
    "mq135_raw": 420,
    "air_quality_level": "NORMAL",
    "gas_alert": false
  },
  "firmware_version": "0.2.0",
  "closest_hazard": null
}
```

---

## 4. Kamus Data Payload

| Field | Tipe Data | Satuan | Keterangan |
| :--- | :--- | :--- | :--- |
| `message_id` | `string` | ID Unik | Format: `HELMET-{WORKER_ID}-{MAC}-{MILLIS}`. Dipakai untuk ACK dan deduplikasi backend. |
| `device_id` | `string` | ID Perangkat | Identitas fisik unit helm (`HELMET-W01`). |
| `worker_id` | `string` | ID Pekerja | ID pekerja yang ditugaskan ke helm (`W01`). |
| `timestamp` | `string` | ISO 8601 UTC | Waktu riil pengambilan data tersinkronisasi NTP (`YYYY-MM-DDTHH:MM:SSZ`). |
| `acceleration.x/y/z` | `float` | $\text{m/s}^2$ | Akselerasi linier 3-sumbu MPU-6050 (tegak diam $a_z \approx 9.81 \text{ m/s}^2$). |
| `gyroscope.x/y/z` | `float` | $\text{deg/s}$ | Kecepatan sudut rotasi kepala 3-sumbu MPU-6050. |
| `orientation.pitch/roll/yaw` | `float` | Derajat ($^\circ$) | Estimasi sudut kemiringan kepala (pitch: menunduk/mendongak, roll: miring kiri/kanan). |
| `impact_g` | `float` | Satuan $g$ | Resultan gaya gravitasi instan: $\sqrt{a_x^2 + a_y^2 + a_z^2} / 9.80665$. Normal berdiri $\approx 1.0g$. |
| `impact_detected` | `boolean` | Flag | `true` jika $g \ge 3.5g$ (benturan keras terdeteksi). |
| `fall_detected` | `boolean` | Flag | `true` jika $g \le 0.45g$ (kondisi melayang/jatuh bebas terdeteksi). |
| `temperature` | `float` | $^\circ\text{C}$ | Suhu aktual sensor DHT22. |
| `humidity` | `float` | $\%$ | Kelembapan relatif sensor DHT22. |
| `air_quality.mq135_raw` | `integer` | $0 - 4095$ | Nilai tegangan mentah ADC 12-bit sensor MQ-135. |
| `air_quality.air_quality_level` | `string` | Enum | `NORMAL`, `MODERATE`, `POOR`, atau `DANGEROUS`. |
| `air_quality.gas_alert` | `boolean` | Flag | `true` jika level kualitas udara masuk `POOR` atau `DANGEROUS`. |
| `firmware_version` | `string` | SemVer | Versi firmware Arduino helm (`0.2.0`). |
| `closest_hazard` | `object` / `null` | Objek / Null | `null` jika aman. Jika ada ancaman, memuat rincian hazard terdekat dengan prioritas tertinggi. |
| `closest_hazard.hazard_id` | `string` | ID Mesin | ID hazard K3 (contoh: `M-FLK-01`, `S-LSR-01`). |
| `closest_hazard.hazard_type` | `string` | Enum Tipe | `FORKLIFT`, `CONTAINER_CRANE`, `AGV`, `TRUCK`, `LASER`, `GRINDING`, `PRESS`, `CNC`, `MACHINERY`. |
| `closest_hazard.hazard_category` | `string` | `MOBILE` / `STATIONARY` | Kategori alat: `MOBILE` (mesin bergerak) atau `STATIONARY` (mesin stasioner diam). |
| `closest_hazard.operating_status` | `string` | `ACTIVE` / `IDLE` | Status operasi mesin yang memancarkan beacon BLE. |
| `closest_hazard.rssi` | `integer` | $\text{dBm}$ | Kekuatan sinyal BLE terfilter (*Smoothed RSSI*). |
| `closest_hazard.proximity_level` | `string` | Enum Jarak | `SAFE`, `MODERATE`, `HIGH`, atau `CRITICAL`. |

---

## 5. Perintah Warning Masuk (Server $\to$ Helm)

Helm berlangganan topik kontrol: `REKSA/helmet/{WORKER_ID}/warning`.

Contoh payload perintah alarm dari supervisor/backend:
```json
{
  "worker_id": "W01",
  "warning_level": "CRITICAL",
  "actions": {
    "vibration": true,
    "buzzer": true
  },
  "duration_ms": 3000,
  "reason": "Uji peringatan helm IoT oleh supervisor"
}
```

---

## 6. Nilai Ambang Batas (Thresholds) Aktual Sistem

Konstanta numerik berikut diambil langsung dari firmware C++ ESP32 dan backend Python:

### A. Sensor Gerak, Benturan, & Jatuh (MPU-6050)
- **Skala Akselerometer:** $\pm 8g$ (`MPU6050_ACCEL_SCALE = 4096.0 LSB/g`)
- **Skala Giroskop:** $\pm 500^\circ/\text{s}$ (`MPU6050_GYRO_SCALE = 65.5 LSB/(deg/s)`)
- **Ambang Benturan (`impact_detected`):** $\ge 3.5g$ (`IMPACT_THRESHOLD_G`)
- **Ambang Jatuh Bebas (`fall_detected`):** $\le 0.45g$ (`FALL_FREEFALL_THRESHOLD_G`)
- **Ambang Kemiringan Rebah (`tilt_threshold`):** $\ge 60.0^\circ$ (`FALL_TILT_THRESHOLD_DEG`)
- **Interval Polling:** $250\text{ ms}$

### B. Kualitas Udara (MQ-135)
- **`NORMAL`:** $\text{ADC} < 1200$ (`gas_alert = false`)
- **`MODERATE`:** $1200 \le \text{ADC} < 1800$ (`gas_alert = false`)
- **`POOR`:** $1800 \le \text{ADC} < 2500$ (`gas_alert = true`, wajib masker/respirator)
- **`DANGEROUS`:** $\text{ADC} \ge 2500$ (`gas_alert = true`, evakuasi wajib)

### C. Suhu Lingkungan (DHT22)
- **`NORMAL`:** $< 30.0^\circ\text{C}$
- **`MODERATE`:** $30.0^\circ\text{C} - 34.9^\circ\text{C}$
- **`TINGGI` / `HIGH`:** $\ge 35.0^\circ\text{C}$
- **Interval Polling:** $2500\text{ ms}$

### D. Jarak Kedekatan BLE Dual-Profile K3 (NimBLE Proximity)

| Zona Bahaya | Mobile Hazard (Forklift, Crane, AGV, Truck) | Stationary Hazard (Laser, Gerinda, Mesin) | Respon Fisik Helm (Buzzer & Vibrasi) |
| :--- | :--- | :--- | :--- |
| **`CRITICAL`** | $\text{RSSI} \ge -70\text{ dBm}$ (Jarak $\approx 3.5\text{ m}$) | $\text{RSSI} \ge -65\text{ dBm}$ (Jarak $\approx 1.2\text{ m}$) | **Menyala Terus (*Continuous*)** |
| **`HIGH`** | $\text{RSSI} \ge -78\text{ dBm}$ (Jarak $\approx 6.0\text{ m}$) | $\text{RSSI} \ge -74\text{ dBm}$ (Jarak $\approx 2.5\text{ m}$) | **Berdenyut Cepat (200ms ON / 100ms OFF)** |
| **`MODERATE`** | $\text{RSSI} \ge -86\text{ dBm}$ (Jarak $\approx 10.0\text{ m}$) | $\text{RSSI} \ge -82\text{ dBm}$ (Jarak $\approx 4.0\text{ m}$) | Padam (Monitoring visual dashboard) |
| **`SAFE`** | $\text{RSSI} < -86\text{ dBm}$ | $\text{RSSI} < -82\text{ dBm}$ | Padam (Operasional normal) |

- **Stabilisasi Sinyal BLE:**
  - *Moving Average Window:* 5 sampel (`RSSI_WINDOW_SIZE = 5`)
  - *Hysteresis:* 3 dBm (`RSSI_HYSTERESIS_DB = 3`) untuk mencegah flapping status.
  - *Consecutive Readings:* 2 pembacaan berturut-turut (`REQUIRED_CONSECUTIVE_READINGS = 2`).
  - *Hazard Timeout:* 6000 ms (6 detik) sebelum hazard dianggap tidak aktif.

### E. Scoring & Override Risiko di Backend (`mqtt_handler.py`)
- **Base Score Proximity:**
  - `CRITICAL` $\to 92$ / 100
  - `HIGH` $\to 72$ / 100
  - `MODERATE` $\to 45$ / 100
  - `SAFE` $\to 15$ / 100
- **Logika Override Darurat:**
  - Jika `fall_detected == true` $\to$ Level `CRITICAL`, Skor = $\max(\text{skor}, 96)$
  - Jika `impact == true` $\to$ Level `CRITICAL`, Skor = $\max(\text{skor}, 94)$
  - Jika udara `DANGEROUS` $\to$ Level `CRITICAL`, Skor = $\max(\text{skor}, 90)$
  - Jika udara `POOR` $\to$ Level `HIGH`, Skor = $\max(\text{skor}, 70)$
- **Batas Cooldown Near-Miss:** 20 detik per pasangan `(worker_id, hazard_id)` untuk mencegah spam duplikasi event.
