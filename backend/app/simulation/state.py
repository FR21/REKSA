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
    sample_rssis = [-88, -82, -75, -68, -60, -84]
    for index, name in enumerate(NAMES, start=1):
        hazard = hazards[(index - 1) % len(hazards)]
        rssi_val = sample_rssis[index - 1]
        dur_val = index * 9
        hz_status = hazard["status"]
        is_mobile = hazard.get("category", "MOBILE") == "MOBILE"

        crit_thresh = -70 if is_mobile else -65
        high_thresh = -78 if is_mobile else -74
        mod_thresh = -86 if is_mobile else -82

        if rssi_val >= crit_thresh:
            prox_level = "CRITICAL"
            base_calc = 75 + max(0, rssi_val - crit_thresh) * 2
        elif rssi_val >= high_thresh:
            prox_level = "HIGH"
            base_calc = 50 + (rssi_val - high_thresh) * 3
        elif rssi_val >= mod_thresh:
            prox_level = "MODERATE"
            base_calc = 25 + (rssi_val - mod_thresh) * 3
        else:
            prox_level = "SAFE"
            base_calc = max(8, 15 + (rssi_val + 95) * 1.5)

        mod_val = 1.2 if hz_status == "MOVING" else 1.1 if hz_status == "ACTIVE" else 0.7 if hz_status == "IDLE" else 0.5
        dur_bonus = min(12, dur_val // 6)
        calc_score = int(min(98, max(5, (base_calc * mod_val) + dur_bonus)))
        calc_level = "CRITICAL" if calc_score >= 75 else "HIGH" if calc_score >= 50 else "MODERATE" if calc_score >= 25 else "SAFE"

        if index == 6:
            calc_score = 0
            calc_level = "SAFE"
            prox_level = "SAFE"

        if index == 5:
            worker_advisory = {
                "status": "READY",
                "escalation_probability": 0.94,
                "risk_level": "HIGH",
                "dominant_factors": ["rapid_rssi_increase", "danger_zone_duration_high", "hazard_active"],
                "recommendation": "Peringatan eskalasi bahaya: Jarak pekerja mendekati zona gerinda aktif dalam jarak sangat dekat.",
                "inference_source": "RANDOM_FOREST_FORECASTER",
                "model_version": "1.0.0",
                "probability_is_calibrated": True,
                "score_semantics": "CALIBRATED_PROBABILITY",
                "advisory_only": True,
                "anomaly": {
                    "engine": "OPERATIONAL_ANOMALY_DETECTOR",
                    "decision_score": -0.048,
                    "is_anomaly": True,
                    "status": "ANOMALOUS",
                    "alert_flag": "ANOMALY_FLAG_1",
                    "inference_source": "ISOLATION_FOREST_OPERATIONAL_ANOMALY",
                    "model_version": "1.0.0",
                    "advisory_only": True,
                    "generated_at": now_iso(),
                },
                "generated_at": now_iso(),
            }
        elif index == 3:
            worker_advisory = {
                "status": "READY",
                "escalation_probability": 0.42,
                "risk_level": "MEDIUM",
                "dominant_factors": ["strong_ble_proximity", "danger_zone_duration_high"],
                "recommendation": "Pekerja berada di perimeter forklift aktif. Pertahankan jarak aman.",
                "inference_source": "RANDOM_FOREST_FORECASTER",
                "model_version": "1.0.0",
                "probability_is_calibrated": True,
                "score_semantics": "CALIBRATED_PROBABILITY",
                "advisory_only": True,
                "anomaly": {
                    "engine": "OPERATIONAL_ANOMALY_DETECTOR",
                    "decision_score": 0.124,
                    "is_anomaly": False,
                    "status": "NORMAL",
                    "alert_flag": "NORMAL",
                    "inference_source": "ISOLATION_FOREST_OPERATIONAL_ANOMALY",
                    "model_version": "1.0.0",
                    "advisory_only": True,
                    "generated_at": now_iso(),
                },
                "generated_at": now_iso(),
            }
        elif index == 2:
            worker_advisory = {
                "status": "READY",
                "escalation_probability": 0.08,
                "risk_level": "LOW",
                "dominant_factors": [],
                "recommendation": "Risiko pendekatan terpantau aman. Tidak diperlukan tindakan korektif.",
                "inference_source": "RANDOM_FOREST_FORECASTER",
                "model_version": "1.0.0",
                "probability_is_calibrated": True,
                "score_semantics": "CALIBRATED_PROBABILITY",
                "advisory_only": True,
                "anomaly": {
                    "engine": "OPERATIONAL_ANOMALY_DETECTOR",
                    "decision_score": 0.185,
                    "is_anomaly": False,
                    "status": "NORMAL",
                    "alert_flag": "NORMAL",
                    "inference_source": "ISOLATION_FOREST_OPERATIONAL_ANOMALY",
                    "model_version": "1.0.0",
                    "advisory_only": True,
                    "generated_at": now_iso(),
                },
                "generated_at": now_iso(),
            }
        else:
            worker_advisory = {
                "status": "AWAITING_LIVE_TELEMETRY",
                "advisory_only": True,
                "generated_at": now_iso(),
            }

        workers.append({
            "id": f"W{index:02}", "name": name, "role": "Operator", "area": AREAS[index - 1],
            "risk_score": calc_score, "risk_level": calc_level, "closest_hazard": hazard["id"],
            "hazard_name": hazard["name"], "hazard_type": hazard["type"], "hazard_category": hazard.get("category", "MOBILE"), "hazard_status": hz_status,
            "rssi": rssi_val, "smoothed_rssi": rssi_val,
            "proximity": prox_level,
            "exposure_seconds": dur_val, "movement": "BERGERAK", "impact": False,
            "fall_detected": False, "impact_g": 1.0, "mq135_raw": 850,
            "air_quality_level": "NORMAL", "gas_alert": False,
            "temperature": round(29 + index * .55, 1), "humidity": round(63 + index * 1.2, 1),
            "online": index != 6, "last_update": now_iso(),
            "calculation_source": "RULE_BASED_SCORING",
            "dominant_factor": "Paparan bahaya" if calc_score > 40 else "Durasi kerja",
            "recommended_action": "Peringatkan pekerja dan kurangi paparan bahaya." if calc_score >= 50 else "Lanjutkan pemantauan normal.",
            "ai_advisory": worker_advisory,
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
