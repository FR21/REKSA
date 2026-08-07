# Arduino Helm Output

Firmware `arduino/helm_v1/helm_v1.ino` menghasilkan dua jenis output:

1. Log teks di Serial Monitor untuk debugging manusia.
2. Payload JSON MQTT untuk web/backend dan pengecekan risiko otomatis.

Untuk pengecekan otomatis, gunakan payload MQTT JSON karena strukturnya stabil.

## Serial monitor startup

Baud rate:

```text
115200
```

Contoh saat boot:

```text
Memulai REKSA Smart Helmet Node...
Buzzer dikonfigurasi pada GPIO 19
Vibration dikonfigurasi pada GPIO 23
DHT22 dikonfigurasi pada GPIO 18
BLE Scanner aktif
Menghubungkan ke WiFi: Shaaapayaaa
WiFi terhubung!
IP Address: 10.168.239.50
```

Jika WiFi gagal:

```text
WiFi gagal terhubung (akan dicoba kembali).
```

## Serial monitor MQTT

Jika berhasil connect MQTT:

```text
Menghubungkan ke Broker MQTT...Terhubung!
Subscribed ke topic: REKSA/helmet/W01/warning
```

Jika gagal connect MQTT:

```text
Menghubungkan ke Broker MQTT...Gagal, status=-4 coba lagi dalam 2 detik...
```

Kode status umum dari PubSubClient:

```text
0   MQTT_CONNECTED
-1  MQTT_DISCONNECTED
-2  MQTT_CONNECT_FAILED
-3  MQTT_CONNECTION_LOST
-4  MQTT_CONNECTION_TIMEOUT
```

Jika publish MQTT berhasil:

```text
Mempublikasikan sensor ke REKSA/helmet/W01/sensor (512 bytes): {"message_id":"msg-12345",...}
```

Jika publish gagal:

```text
Gagal mempublikasikan sensor ke MQTT. connected=1, state=0, payload=620 bytes, buffer=1024 bytes
```

## Serial monitor environment

Jika DHT22 valid:

```text
========== KONDISI LINGKUNGAN ==========
Suhu        : 25.8 °C
Kelembapan  : 61.7 %
Status suhu : NORMAL
========================================
```

Status suhu:

```text
NORMAL    temperature < 30.0
MODERATE  temperature >= 30.0
TINGGI    temperature >= 35.0
```

Jika DHT22 belum valid:

```text
Status      : Data DHT22 belum tersedia
```

## Serial monitor hazard

Jika tidak ada hazard:

```text
========== DAFTAR HAZARD ==========
Tidak ada hazard REKSA yang aktif.
===================================
```

Jika hazard ditemukan:

```text
Hazard baru ditemukan: REKSA_HAZARD_F01
```

Daftar hazard aktif:

```text
========== DAFTAR HAZARD ==========
Nama         : REKSA_HAZARD_F01
MAC          : aa:bb:cc:dd:ee:ff
RSSI mentah  : -61 dBm
RSSI rata-rata: -63 dBm
Zona         : HIGH
-----------------------------------

HAZARD PRIORITAS:
Nama : REKSA_HAZARD_F01
RSSI : -63 dBm
Zona : HIGH
===================================
```

Jika zona berubah:

```text
Perubahan zona REKSA_HAZARD_F01: MODERATE -> HIGH
```

Jika hazard hilang lebih dari timeout:

```text
Hazard tidak aktif: REKSA_HAZARD_F01
```

## Serial monitor warning

```text
========== STATUS WARNING ==========
Level      : CRITICAL
Buzzer     : MENYALA TERUS
Vibration  : MENYALA TERUS
====================================
```

Level warning:

```text
TANPA HAZARD
SAFE
MODERATE
HIGH
CRITICAL
```

Output fisik:

```text
HIGH      buzzer dan vibration pulse cepat
CRITICAL  buzzer dan vibration menyala terus
SAFE      buzzer dan vibration mati
MODERATE  buzzer dan vibration mati
```

## MQTT payload helm

Topic:

```text
REKSA/helmet/W01/sensor
```

Publish interval:

```text
2500 ms
```

Payload tanpa hazard:

```json
{
  "message_id": "msg-12345",
  "device_id": "HELMET-W01",
  "worker_id": "W01",
  "timestamp": "2026-08-07T14:10:25Z",
  "acceleration": { "x": 0.12, "y": 0.04, "z": 9.81 },
  "gyroscope": { "x": 0.8, "y": 0.2, "z": 0.1 },
  "orientation": { "pitch": -0.7, "roll": 1.1, "yaw": 0 },
  "impact_detected": false,
  "fall_detected": false,
  "impact_g": 1.01,
  "temperature": 25.8,
  "humidity": 61.7,
  "air_quality": {
    "mq135_raw": 920,
    "air_quality_level": "NORMAL",
    "gas_alert": false
  },
  "firmware_version": "0.2.0",
  "closest_hazard": null
}
```

Payload dengan hazard:

```json
{
  "message_id": "msg-12345",
  "device_id": "HELMET-W01",
  "worker_id": "W01",
  "timestamp": "2026-08-07T14:10:25Z",
  "acceleration": { "x": 0.12, "y": 0.04, "z": 9.81 },
  "gyroscope": { "x": 0.8, "y": 0.2, "z": 0.1 },
  "orientation": { "pitch": -0.7, "roll": 1.1, "yaw": 0 },
  "impact_detected": false,
  "fall_detected": false,
  "impact_g": 1.01,
  "temperature": 25.8,
  "humidity": 61.7,
  "air_quality": {
    "mq135_raw": 920,
    "air_quality_level": "NORMAL",
    "gas_alert": false
  },
  "firmware_version": "0.2.0",
  "closest_hazard": {
    "hazard_id": "F01",
    "hazard_type": "FORKLIFT",
    "operating_status": "ACTIVE",
    "rssi": -63,
    "proximity_level": "HIGH"
  }
}
```

## Field penting untuk pengecekan risiko

```text
worker_id                  ID pekerja, contoh W01
device_id                  ID helm, contoh HELMET-W01
timestamp                  waktu payload
temperature                suhu DHT22 jika valid
humidity                   kelembapan DHT22 jika valid
acceleration               akselerasi MPU6050 dalam m/s2
gyroscope                  kecepatan sudut MPU6050 dalam deg/s
orientation                pitch/roll estimasi dari MPU6050
impact_g                   total akselerasi dalam satuan g
air_quality.mq135_raw      nilai ADC MQ135 0-4095
air_quality.air_quality_level UNKNOWN, NORMAL, MODERATE, POOR, DANGEROUS
air_quality.gas_alert      true jika udara POOR atau DANGEROUS
closest_hazard             null jika aman/tidak ada hazard
closest_hazard.hazard_id   ID mesin, contoh F01
closest_hazard.hazard_type FORKLIFT, GRINDING, atau LASER
closest_hazard.rssi        kekuatan sinyal BLE, makin mendekati 0 berarti makin dekat
closest_hazard.proximity_level SAFE, MODERATE, HIGH, CRITICAL
impact_detected            status benturan helm
fall_detected              status jatuh
```

Aturan sederhana untuk pengecekan risiko:

```text
closest_hazard == null              -> tidak ada hazard terdekat
proximity_level == HIGH             -> peringatan tinggi
proximity_level == CRITICAL         -> kondisi kritis
temperature >= 35                   -> panas tinggi
impact_detected == true             -> indikasi benturan
fall_detected == true               -> indikasi jatuh
air_quality_level == POOR           -> udara buruk
air_quality_level == DANGEROUS      -> udara berbahaya
```

## MQTT command dari web ke helm

Helm subscribe:

```text
REKSA/helmet/W01/warning
```

Contoh command:

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

Saat diterima, Serial Monitor menampilkan:

```text
Pesan MQTT diterima [REKSA/helmet/W01/warning]
Peringatan masuk: level=CRITICAL, buzzer=1, vibration=1
```
