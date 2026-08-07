import logging
from datetime import UTC, datetime
from typing import Any

from app.services.websocket_service import websocket_manager
from app.simulation.engine import simulation_engine

logger = logging.getLogger(__name__)


async def handle_mqtt_message(topic: str, payload: dict[str, Any]) -> None:
    try:
        parts = topic.split("/")
        if len(parts) < 3:
            return

        category = parts[1]  # e.g. helmet, hazard, environment
        now = datetime.now(UTC).isoformat()

        if category == "helmet":
            worker_id = parts[2]
            # Find the worker in state
            worker = next((w for w in simulation_engine.state["workers"] if w["id"] == worker_id), None)
            if worker:
                air_quality = payload.get("air_quality") or {}
                # Update worker state
                worker.update({
                    "online": True,
                    "impact": payload.get("impact_detected", False),
                    "fall_detected": payload.get("fall_detected", False),
                    "impact_g": payload.get("impact_g", worker.get("impact_g", 1.0)),
                    "mq135_raw": air_quality.get("mq135_raw", worker.get("mq135_raw", 0)),
                    "air_quality_level": air_quality.get(
                        "air_quality_level",
                        worker.get("air_quality_level", "UNKNOWN"),
                    ),
                    "gas_alert": air_quality.get("gas_alert", worker.get("gas_alert", False)),
                    "temperature": (
                        payload.get("temperature")
                        if payload.get("temperature") is not None
                        else worker.get("temperature")
                    ),
                    "humidity": (
                        payload.get("humidity")
                        if payload.get("humidity") is not None
                        else worker.get("humidity")
                    ),
                    "last_update": now,
                    "calculation_source": "HARDWARE_MQTT",
                })

                # Process closest hazard if present
                closest_hazard = payload.get("closest_hazard")
                if closest_hazard:
                    hz_id = closest_hazard.get("hazard_id")
                    hz_type = closest_hazard.get("hazard_type", "FORKLIFT")
                    hz_status = closest_hazard.get("operating_status", "ACTIVE")
                    rssi = closest_hazard.get("rssi", -100)
                    proximity = closest_hazard.get("proximity_level", "SAFE")

                    # Find hazard name
                    hz = next((h for h in simulation_engine.state["hazards"] if h["id"] == hz_id), None)
                    hz_name = hz["name"] if hz else f"Hazard {hz_id}"

                    # Map proximity to risk level and score
                    risk_level = proximity.upper()
                    if risk_level == "CRITICAL":
                        risk_score = 92
                    elif risk_level == "HIGH":
                        risk_score = 72
                    elif risk_level == "MODERATE":
                        risk_score = 45
                    else:
                        risk_score = 15

                    worker.update({
                        "closest_hazard": hz_id,
                        "hazard_name": hz_name,
                        "hazard_type": hz_type,
                        "hazard_status": hz_status,
                        "rssi": rssi,
                        "smoothed_rssi": rssi,
                        "proximity": proximity,
                        "risk_level": risk_level,
                        "risk_score": risk_score,
                        "dominant_factor": "Paparan bahaya (Hardware)",
                    })

                    # Check if near miss needs to be created
                    if risk_level == "CRITICAL" and not simulation_engine._near_miss_created:
                        event = {
                            "id": f"NM-{datetime.now(UTC).strftime('%H%M%S')}",
                            "timestamp": now,
                            "worker_id": worker_id,
                            "worker_name": worker["name"],
                            "hazard_id": hz_id,
                            "hazard_name": hz_name,
                            "hazard_type": hz_type,
                            "proximity": "CRITICAL",
                            "rssi": rssi,
                            "duration": 5.0,  # default hardware duration
                            "hazard_status": hz_status,
                            "risk_score": risk_score,
                            "risk_level": "CRITICAL",
                            "warning_status": "DELIVERED",
                            "acknowledged": False,
                            "note": "",
                        }
                        simulation_engine.state["near_misses"].insert(0, event)
                        simulation_engine._near_miss_created = True
                        await websocket_manager.broadcast("near_miss.created", event)
                else:
                    worker.update({
                        "closest_hazard": None,
                        "hazard_name": "-",
                        "hazard_type": "-",
                        "hazard_status": "INACTIVE",
                        "rssi": -100,
                        "smoothed_rssi": -100,
                        "proximity": "SAFE",
                        "risk_level": "SAFE",
                        "risk_score": 10,
                    })

                if worker.get("fall_detected"):
                    worker.update({
                        "risk_level": "CRITICAL",
                        "risk_score": max(worker["risk_score"], 96),
                        "dominant_factor": "Deteksi jatuh helm",
                        "recommended_action": "Periksa pekerja segera dan hentikan aktivitas di area.",
                    })
                elif worker.get("impact"):
                    worker.update({
                        "risk_level": "CRITICAL",
                        "risk_score": max(worker["risk_score"], 94),
                        "dominant_factor": "Benturan helm terdeteksi",
                        "recommended_action": "Periksa kondisi pekerja dan helm sebelum melanjutkan kerja.",
                    })
                elif worker.get("air_quality_level") == "DANGEROUS":
                    worker.update({
                        "risk_level": "CRITICAL",
                        "risk_score": max(worker["risk_score"], 90),
                        "dominant_factor": "Kualitas udara berbahaya",
                        "recommended_action": "Evakuasi pekerja dari area dan periksa ventilasi.",
                    })
                elif worker.get("air_quality_level") == "POOR" and worker["risk_level"] != "CRITICAL":
                    worker.update({
                        "risk_level": "HIGH",
                        "risk_score": max(worker["risk_score"], 70),
                        "dominant_factor": "Kualitas udara buruk",
                        "recommended_action": "Periksa ventilasi dan kurangi paparan pekerja.",
                    })

                # Broadcast updated worker
                await websocket_manager.broadcast("worker.updated", worker)

                # Also update corresponding device in state
                dev_id = f"HELMET-{worker_id}"
                device = next((d for d in simulation_engine.state["devices"] if d["id"] == dev_id), None)
                if device:
                    device.update({
                        "online": True,
                        "last_seen": now,
                        "latest_message": now,
                        "signal": 90,
                    })
                    await websocket_manager.broadcast("device.paired", device)

        elif category == "hazard":
            hazard_id = parts[2]
            hazard = next((h for h in simulation_engine.state["hazards"] if h["id"] == hazard_id), None)
            if hazard:
                hazard.update({
                    "online": True,
                    "status": payload.get("operating_status", hazard.get("status", "ACTIVE")),
                    "last_update": now,
                })
                # Update corresponding device
                dev_id = f"HAZARD-{hazard_id}"
                device = next((d for d in simulation_engine.state["devices"] if d["id"] == dev_id), None)
                if device:
                    device.update({
                        "online": True,
                        "last_seen": now,
                        "latest_message": now,
                    })
                    await websocket_manager.broadcast("device.paired", device)

        elif category == "environment":
            env_id = parts[2]
            # Find environment device
            dev_id = f"ENV-{env_id}"
            device = next((d for d in simulation_engine.state["devices"] if d["id"] == dev_id), None)
            if device:
                device.update({
                    "online": True,
                    "last_seen": now,
                    "latest_message": now,
                })
                await websocket_manager.broadcast("device.paired", device)

    except Exception as e:
        logger.error("Error processing MQTT message: %s", e)
