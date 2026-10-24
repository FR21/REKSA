# REST and WebSocket API

Base REST path: `/api/v1`. Dokumentasi interaktif tersedia di `/docs` dan `/redoc`.

Kelompok endpoint aktif: system, dashboard, workers, hazards, near-misses, devices, analytics, risk, settings, simulation reset, dan warnings. Daftar kontrak aktual dapat diekspor dari `/openapi.json`.

### Tingkat Risiko K3 (Risk Levels)
API REST dan streaming WebSocket menggunakan 5 status risiko terstandarisasi:
- `SAFE`: Kondisi aman normal (skor 0–39).
- `MODERATE`: Peringatan jarak mendekati batas perimeter bahaya (skor 40–69).
- `HIGH`: Ancaman jarak dekat, butuh tindakan pencegahan (skor 70–89).
- `CRITICAL`: Jarak pengereman darurat / titik jepit kritis (skor 90–100, alarm lokal helm aktif).
- `RECOVERY`: Mode pemulihan paska keluar dari zona bahaya atau tindakan `POST /workers/{id}/mark-safe` (alarm dihentikan, event ditutup, durasi dihitung).

WebSocket berada di `WS /ws/live`. Envelope konsisten:

```json
{"event":"risk.updated","timestamp":"2026-08-03T14:30:00+07:00","data":{}}
```

Client mengirim string `ping` tiap 15 detik dan menerima event `heartbeat`. Reconnect memakai exponential backoff maksimum 30 detik dan event dideduplikasi sebelum masuk store UI.
