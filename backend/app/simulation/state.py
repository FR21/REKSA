from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any

NAMES = ["Andi Pratama", "Siti Rahma", "Budi Santoso", "Dewi Lestari", "Rizky Maulana", "Nadia Putri"]
AREAS = ["Gudang Utama", "Zona Bongkar", "Produksi A", "Produksi B", "Koridor Timur", "Area Laser"]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_state(seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)
    workers: list[dict[str, Any]] = []
    hazards = [
        {"id": "M-FLK-01", "name": "Forklift Alpha", "type": "FORKLIFT", "category": "MOBILE", "status": "MOVING", "online": True, "area": "Gudang Utama", "alias": "F01", "beacon_name": "RK_M_FLK01"},
        {"id": "M-FLK-02", "name": "Forklift Bravo", "type": "FORKLIFT", "category": "MOBILE", "status": "IDLE", "online": True, "area": "Zona Bongkar", "alias": "F02", "beacon_name": "RK_M_FLK02"},
        {"id": "M-FLK-03", "name": "Forklift Charlie", "type": "FORKLIFT", "category": "MOBILE", "status": "MOVING", "online": True, "area": "Gudang Utama", "alias": "F03", "beacon_name": "RK_M_FLK03"},
        {"id": "M-CNT-01", "name": "Reach Stacker C01", "type": "CONTAINER_CRANE", "category": "MOBILE", "status": "MOVING", "online": True, "area": "Zona Bongkar", "alias": "C01", "beacon_name": "RK_M_CNT01"},
        {"id": "S-GRD-01", "name": "Gerinda Stasiun 1", "type": "GRINDING", "category": "STATIONARY", "status": "ACTIVE", "online": True, "area": "Produksi A", "alias": "G01", "beacon_name": "RK_S_GRD01"},
        {"id": "S-LSR-01", "name": "Laser Cutter 1", "type": "LASER", "category": "STATIONARY", "status": "ACTIVE", "online": True, "area": "Area Laser", "alias": "L01", "beacon_name": "RK_S_LSR01"},
    ]
    for index, name in enumerate(NAMES, start=1):
        base_score = [18, 32, 56, 12, 67, 27][index - 1]
        level = "SAFE" if base_score < 25 else "MODERATE" if base_score < 50 else "HIGH"
        hazard = hazards[(index - 1) % len(hazards)]
        workers.append({
            "id": f"W{index:02}", "name": name, "role": "Operator", "area": AREAS[index - 1],
            "risk_score": base_score, "risk_level": level, "closest_hazard": hazard["id"],
            "hazard_name": hazard["name"], "hazard_type": hazard["type"], "hazard_category": hazard.get("category", "MOBILE"), "hazard_status": hazard["status"],
            "rssi": -78 + index * 4, "smoothed_rssi": -78 + index * 4,
            "proximity": "SAFE" if index == 1 else "MODERATE" if index < 5 else "HIGH",
            "exposure_seconds": index * 9, "movement": "BERGERAK", "impact": False,
            "fall_detected": False, "impact_g": 1.0, "mq135_raw": 850,
            "air_quality_level": "NORMAL", "gas_alert": False,
            "temperature": round(29 + index * .55, 1), "humidity": round(63 + index * 1.2, 1),
            "online": index != 6, "last_update": now_iso(),
            "calculation_source": "RULE_BASED_SCORING",
            "dominant_factor": "Paparan bahaya" if base_score > 40 else "Durasi kerja",
            "recommended_action": "Peringatkan pekerja dan kurangi paparan bahaya." if base_score >= 50 else "Lanjutkan pemantauan normal.",
            "ai_advisory": {
                "status": "AWAITING_LIVE_TELEMETRY",
                "advisory_only": True,
                "generated_at": now_iso(),
            },
        })

    devices: list[dict[str, Any]] = []
    for worker in workers:
        devices.append({"id": f"DEV-HLM-{worker['id']}", "type": "SMART_HELMET", "assignment": worker["name"], "online": worker["online"], "last_seen": now_iso(), "firmware": "0.2.0", "signal": 82 if worker["online"] else 0, "topic": f"REKSA/helmet/{worker['id']}/sensor", "latest_message": now_iso()})
    for hazard in hazards:
        dev_type = "HAZARD_MOBILE" if hazard.get("category") == "MOBILE" else "HAZARD_STATIONARY"
        devices.append({"id": f"DEV-BCN-{hazard['id']}", "type": dev_type, "assignment": hazard["name"], "online": hazard["online"], "last_seen": now_iso(), "firmware": "0.2.0", "signal": 76, "topic": f"REKSA/hazard/{hazard['id']}/beacon", "latest_message": now_iso()})

    near_misses = []
    for index in range(8):
        worker = workers[index % len(workers)]
        hazard = hazards[index % len(hazards)]
        near_misses.append({
            "id": f"NM-{2401 + index}", "timestamp": (datetime.now(UTC) - timedelta(hours=index * 7 + 1)).isoformat(),
            "worker_id": worker["id"], "worker_name": worker["name"], "hazard_id": hazard["id"],
            "hazard_name": hazard["name"], "hazard_type": hazard["type"], "proximity": "CRITICAL",
            "rssi": -39 - index, "duration": 6.2 + index * .4, "hazard_status": "MOVING" if hazard["type"] == "FORKLIFT" else "ACTIVE",
            "risk_score": 78 + index % 17, "risk_level": "CRITICAL", "warning_status": "DELIVERED",
            "acknowledged": index > 2, "note": "Area telah diperiksa." if index > 2 else "",
        })

    history = []
    for day in range(13, -1, -1):
        date = (datetime.now(UTC) - timedelta(days=day)).date().isoformat()
        history.append({"date": date, "average_risk": rng.randint(25, 52), "near_misses": rng.randint(0, 5), "exposure_minutes": rng.randint(22, 86), "temperature": round(rng.uniform(29, 34), 1), "humidity": round(rng.uniform(62, 76), 1), "uptime": round(rng.uniform(92, 100), 1), "warning_latency": rng.randint(140, 390)})

    return {"workers": workers, "hazards": hazards, "devices": devices, "near_misses": near_misses, "history": history, "activities": [], "warnings": [], "voice_transmissions": []}
