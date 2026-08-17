# MQTT Topics

Semua payload JSON divalidasi dengan Pydantic sebelum diproses. Subscriber backend
memakai QoS 1. Library PubSubClient pada firmware mengirim publish QoS 0, sehingga
REKSA menambahkan ACK aplikasi dan retransmission dengan `message_id` yang tetap.

Deployment cloud wajib memakai MQTT over TLS, kredensial berbeda untuk backend dan
setiap piranti, serta ACL topic. Mosquitto anonymous pada Docker Compose hanya untuk
pengembangan lokal. Backend mendukung `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_TLS`,
`MQTT_CA_CERT`, dan `MQTT_CLIENT_ID`.

ACK telemetry dikirim pada `REKSA/helmet/{worker_id}/telemetry/ack`:

```json
{"message_id":"HELMET-W01-a1b2-12000","accepted":true,"duplicate":false}
```

Helmet mempertahankan payload di buffer dan mengirim ulang sampai ACK diterima.
Backend mendeduplikasi ID. Dalam mode Pub/Sub, bridge baru mengirim ACK setelah
Pub/Sub mengembalikan message ID.

| Direction | Topic | Purpose |
|---|---|---|
| Subscribe | `REKSA/helmet/+/sensor` | Gerak, benturan, hazard terdekat, RSSI |
| Subscribe | `REKSA/helmet/+/status` | Firmware and connectivity |
| Subscribe | `REKSA/helmet/+/warning/ack` | Acknowledgement dari helm |
| Subscribe | `REKSA/hazard/+/beacon` | Beacon dan koordinat simulasi hazard |
| Subscribe | `REKSA/hazard/+/status` | Operating status hazard |
| Subscribe | `REKSA/environment/+/data` | Suhu dan kelembapan |
| Subscribe | `REKSA/event/nearmiss` | Event dari edge node opsional |
| Subscribe | `REKSA/risk/+/score` | Assessment eksternal opsional |
| Publish | `REKSA/helmet/{worker_id}/warning` | Vibration/buzzer command |
| Publish | `REKSA/helmet/{worker_id}/telemetry/ack` | ACK dan deduplikasi telemetry |
| Publish | `REKSA/system/command` | System command |

Payload contoh lengkap tersedia dalam [`web.txt`](../../web.txt). Pesan invalid dicatat secara terpisah dan tidak mengubah device state.

## Smart helmet sync test

Untuk helm fisik, kirim telemetry ke:

```text
REKSA/helmet/W01/sensor
```

Payload minimum yang diterima backend:

```json
{
  "message_id": "msg-1",
  "device_id": "HELMET-W01",
  "worker_id": "W01",
  "timestamp": "2026-08-06T13:00:00Z",
  "acceleration": { "x": 0, "y": 0, "z": 9.8 },
  "gyroscope": { "x": 0, "y": 0, "z": 0 },
  "orientation": { "pitch": 0, "roll": 0, "yaw": 0 },
  "impact_detected": false,
  "fall_detected": false,
  "impact_g": 1.01,
  "closest_hazard": null,
  "temperature": 31.5,
  "humidity": 72,
  "air_quality": {
    "mq135_raw": 920,
    "air_quality_level": "NORMAL",
    "gas_alert": false
  },
  "firmware_version": "0.2.0"
}
```

Jika helm mendeteksi beacon `REKSA_HAZARD_F01`, isi `closest_hazard` seperti ini:

```json
{
  "hazard_id": "F01",
  "hazard_type": "FORKLIFT",
  "operating_status": "ACTIVE",
  "rssi": -62,
  "proximity_level": "HIGH"
}
```

Alur sinkronisasi:

1. ESP32 publish payload JSON ke Mosquitto.
2. Backend subscribe `REKSA/helmet/+/sensor`, validasi payload, lalu update worker `W01`.
3. Backend broadcast event `worker.updated` lewat `WS /ws/live`.
4. Frontend menerima event dan mengganti data live monitoring tanpa refresh manual.
5. Backend menambahkan sampel ke temporal window dan meminta advisory ke REKSA AI.
6. Hasil inference dikirim melalui `ai.forecast.updated` dan `worker.updated`.

Tes cepat tanpa ESP32:

```bash
mosquitto_pub -h localhost -p 1883 -q 1 -t REKSA/helmet/W01/sensor -m '{"message_id":"msg-test","device_id":"HELMET-W01","worker_id":"W01","timestamp":"2026-08-06T13:00:00Z","acceleration":{"x":0,"y":0,"z":9.8},"gyroscope":{"x":0,"y":0,"z":0},"orientation":{"pitch":0,"roll":0,"yaw":0},"impact_detected":false,"fall_detected":false,"impact_g":1.01,"closest_hazard":{"hazard_id":"F01","hazard_type":"FORKLIFT","operating_status":"ACTIVE","rssi":-62,"proximity_level":"HIGH"},"temperature":31.5,"humidity":72,"air_quality":{"mq135_raw":920,"air_quality_level":"NORMAL","gas_alert":false},"firmware_version":"0.2.0"}'
```
