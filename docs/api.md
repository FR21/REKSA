# REST and WebSocket API

Base REST path: `/api/v1`. Dokumentasi interaktif tersedia di `/docs` dan `/redoc`.

Kelompok endpoint aktif: system, dashboard, workers, hazards, near-misses, devices, analytics, risk, settings, simulation reset, dan warnings. Daftar kontrak aktual dapat diekspor dari `/openapi.json`.

WebSocket berada di `WS /ws/live`. Envelope konsisten:

```json
{"event":"risk.updated","timestamp":"2026-08-03T14:30:00+07:00","data":{}}
```

Client mengirim string `ping` tiap 15 detik dan menerima event `heartbeat`. Reconnect memakai exponential backoff maksimum 30 detik dan event dideduplikasi sebelum masuk store UI.
