# Arsitektur REKSA

REKSA menggunakan modular monolith. FastAPI adalah satu-satunya pemilik logika proximity, exposure, near-miss, warning, risk, simulasi, dan agregasi historis. React hanya menampilkan state dan mengirim intent supervisor.

```mermaid
flowchart LR
  H[Smart Helmets] -->|MQTT| M[Eclipse Mosquitto]
  Z[Hazard Nodes] -->|MQTT| M
  E[Environment Nodes] -->|MQTT| M
  S[Seeded Demo State] --> B[FastAPI Modular Monolith]
  M --> B
  B --> P[(PostgreSQL)]
  B -->|REST /api/v1| F[React Dashboard]
  B -->|WS /ws/live| F
  F -->|Supervisor commands| B
  B -->|Warnings via MQTT| H
  B -->|Temporal window| A[REKSA AI Advisory]
  A -->|Forecast + provenance| B
```

AI bersifat **advisory-only**. Warning lokal pada helm dan state machine backend tidak
menunggu respons AI. Bila service AI tidak tersedia, dashboard menampilkan status
`UNAVAILABLE` tanpa membuat probabilitas pengganti.

Domain backend dipisahkan ke `schemas`, `models`, `services`, `simulation`, dan `api`. Deployment tetap empat container agar mudah didemonstrasikan dan dirawat.

## Relasi data

```mermaid
erDiagram
  WORKER ||--o| HELMET_DEVICE : wears
  DEVICE ||--o| HELMET_DEVICE : identifies
  HAZARD ||--o| HAZARD_DEVICE : monitored_by
  DEVICE ||--o| HAZARD_DEVICE : identifies
  WORKER ||--o{ SENSOR_READING : produces
  WORKER ||--o{ PROXIMITY_READING : has
  HAZARD ||--o{ PROXIMITY_READING : observed_in
  WORKER ||--o{ EXPOSURE_SESSION : accumulates
  HAZARD ||--o{ EXPOSURE_SESSION : causes
  EXPOSURE_SESSION ||--o{ NEAR_MISS_EVENT : triggers
  NEAR_MISS_EVENT ||--o| SUPERVISOR_ACKNOWLEDGEMENT : reviewed_by
  WORKER ||--o{ RISK_ASSESSMENT : receives
  WORKER ||--o{ WARNING_EVENT : receives
  ENVIRONMENT_NODE ||--o{ ENVIRONMENT_READING : produces
```
