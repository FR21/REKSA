import logging
from datetime import UTC, datetime
from typing import Any

from app.services.websocket_service import websocket_manager
from app.simulation.engine import simulation_engine

logger = logging.getLogger(__name__)


async def handle_mqtt_message(topic: str, payload: dict[str, Any] | bytes) -> None:
    try:
        parts = topic.split("/")
        if len(parts) < 3:
            return

        category = parts[1]
        now = datetime.now(UTC).isoformat()

        if category == "helmet" and "voice" in parts:
            worker_id = parts[2]
            action = parts[-1]
            from app.services.voice_service import voice_service
            if action == "stream":
                await voice_service.handle_stream(worker_id, payload)
            elif action == "status":
                status = payload.decode('utf-8')
                await voice_service.handle_status(worker_id, status)
            return

        if category == "helmet" and parts[-1] == "status" and "voice" not in parts:
            worker_id = parts[2]
            status_val = payload.get("status") if isinstance(payload, dict) else (payload.decode('utf-8') if isinstance(payload, bytes) else str(payload))
            is_online = payload.get("online", True) if isinstance(payload, dict) else (str(status_val).upper() not in ("OFFLINE", "0", "FALSE", "DISCONNECTED"))
            worker = next((w for w in simulation_engine.state["workers"] if w["id"] == worker_id), None)
            if worker:
                worker["online"] = is_online
                worker["hardware_source"] = True
                worker["last_update"] = now
                if not is_online:
                    worker["risk_level"] = "SAFE"
                    worker["risk_score"] = 0
                    worker["proximity"] = "SAFE"
                    worker["closest_hazard"] = None
                    worker["hazard_name"] = "-"
                    worker["hazard_status"] = "INACTIVE"
                    worker["dominant_factor"] = "Perangkat Offline"
                    worker["recommended_action"] = "Helm keselamatan offline. Pastikan daya perangkat aktif."
                await websocket_manager.broadcast("worker.updated", worker)
            dev_ids = (f"DEV-HLM-{worker_id}", f"HELMET-{worker_id}", worker_id)
            device = next((d for d in simulation_engine.state["devices"] if d["id"] in dev_ids or worker_id in d["id"]), None)
            if device:
                device["online"] = is_online
                device["hardware_source"] = True
                device["last_seen"] = now
                device["latest_message"] = now
                device["signal"] = 90 if is_online else 0
                await websocket_manager.broadcast("device.paired", device)
            return

        if not isinstance(payload, dict):
            return

        if category == "helmet":
            worker_id = parts[2]
            worker = next((w for w in simulation_engine.state["workers"] if w["id"] == worker_id), None)
            if worker:
                air_quality = payload.get("air_quality") or {}
                worker.update({
                    "online": True,
                    "hardware_source": True,
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

                from app.services.db_service import db_service
                await db_service.persist_sensor_reading(
                    worker_id, payload, worker.get("movement", "BERGERAK")
                )

                closest_hazard = payload.get("closest_hazard")
                if closest_hazard:
                    hz_id = closest_hazard.get("hazard_id")
                    hz_type = closest_hazard.get("hazard_type", "FORKLIFT")
                    hz_status = closest_hazard.get("operating_status", "ACTIVE")
                    rssi = closest_hazard.get("rssi", -100)
                    proximity = closest_hazard.get("proximity_level", "SAFE")

                    hz = next(
                        (h for h in simulation_engine.state["hazards"]
                         if h["id"] == hz_id or h.get("alias") == hz_id or h.get("beacon_name") == hz_id),
                        None
                    )
                    hz_name = hz["name"] if hz else f"Hazard {hz_id}"
                    hz_category = closest_hazard.get("hazard_category") or (
                        hz.get("category") if hz else ("MOBILE" if hz_type in ("FORKLIFT", "CONTAINER_CRANE", "AGV", "TRUCK") or str(hz_id).startswith(("M-", "F", "C", "V")) else "STATIONARY")
                    )

                    risk_level = proximity.upper()
                    if risk_level == "CRITICAL":
                        risk_score = 92
                    elif risk_level == "HIGH":
                        risk_score = 72
                    elif risk_level == "MODERATE":
                        risk_score = 45
                    else:
                        risk_score = 15

                    if risk_level == "SAFE":
                        worker.update({
                            "closest_hazard": hz_id,
                            "hazard_name": hz_name,
                            "hazard_type": hz_type,
                            "hazard_category": hz_category,
                            "hazard_status": hz_status,
                            "rssi": rssi,
                            "smoothed_rssi": rssi,
                            "proximity": proximity,
                            "risk_level": risk_level,
                            "risk_score": risk_score,
                            "dominant_factor": "None",
                            "recommended_action": "Kondisi operasional normal. Tetap patuhi protokol K3 dan gunakan APD standar selama berada di area kerja.",
                        })
                    else:
                        rec_action = (
                            "Tinggalkan lintasan alat berat. Jaga jarak aman minimal 10-15 meter dari forklift/kontainer bergerak."
                            if hz_category == "MOBILE"
                            else "Patuhi batas garis aman mesin. Gunakan APD lengkap dan hindari titik jepit (pinch-point) mesin."
                        )
                        worker.update({
                            "closest_hazard": hz_id,
                            "hazard_name": hz_name,
                            "hazard_type": hz_type,
                            "hazard_category": hz_category,
                            "hazard_status": hz_status,
                            "rssi": rssi,
                            "smoothed_rssi": rssi,
                            "proximity": proximity,
                            "risk_level": risk_level,
                            "risk_score": risk_score,
                            "dominant_factor": f"Paparan bahaya {hz_category.capitalize()} (Hardware)",
                            "recommended_action": rec_action,
                        })

                    import time
                    cooldown_key = (worker_id, hz_id)
                    last_time = getattr(simulation_engine, "_near_miss_cooldowns", {}).get(cooldown_key, 0)
                    now_ts = time.time()
                    if risk_level == "CRITICAL" and (now_ts - last_time > 20 or not simulation_engine._near_miss_created):
                        if not hasattr(simulation_engine, "_near_miss_cooldowns"):
                            simulation_engine._near_miss_cooldowns = {}
                        simulation_engine._near_miss_cooldowns[cooldown_key] = now_ts
                        event = {
                            "id": f"NM-{datetime.now(UTC).strftime('%H%M%S')}-{worker_id}",
                            "timestamp": now,
                            "worker_id": worker_id,
                            "worker_name": worker["name"],
                            "hazard_id": hz_id,
                            "hazard_name": hz_name,
                            "hazard_type": hz_type,
                            "proximity": "CRITICAL",
                            "rssi": rssi,
                            "duration": 5.0,
                            "hazard_status": hz_status,
                            "risk_score": risk_score,
                            "risk_level": "CRITICAL",
                            "warning_status": "DELIVERED",
                            "acknowledged": False,
                            "note": "",
                        }
                        simulation_engine.state["near_misses"].insert(0, event)
                        simulation_engine._near_miss_created = True
                        simulation_engine.state.setdefault("activities", []).insert(0, {
                            "id": f"act-nm-{event['id']}",
                            "type": "NEAR_MISS",
                            "message": f"{worker['name']} ({worker_id}) mendekati {hz_name} · RSSI {rssi} dBm",
                            "timestamp": now,
                        })
                        try:
                            from app.api.v1.router import sync_today_history
                            sync_today_history()
                        except Exception:
                            pass
                        await websocket_manager.broadcast("near_miss.created", event)
                        await db_service.persist_near_miss(event)
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
                        "dominant_factor": "None",
                        "recommended_action": "Kondisi operasional normal. Tetap patuhi protokol K3 dan gunakan APD standar selama berada di area kerja.",
                    })

                if worker.get("fall_detected"):
                    worker.update({
                        "risk_level": "CRITICAL",
                        "risk_score": max(worker["risk_score"], 96),
                        "dominant_factor": "Deteksi jatuh helm",
                        "recommended_action": "Periksa pekerja segera di lokasi kejadian dan hentikan seluruh aktivitas sementara di area tersebut.",
                    })
                elif worker.get("impact"):
                    worker.update({
                        "risk_level": "CRITICAL",
                        "risk_score": max(worker["risk_score"], 94),
                        "dominant_factor": "Benturan helm terdeteksi",
                        "recommended_action": "Periksa kondisi fisik pekerja dan integritas helm keselamatan sebelum mengizinkan melanjutkan kerja.",
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

                from app.services.runtime import ai_advisory_service

                ai_advisory = await ai_advisory_service.analyze_helmet_payload(payload)
                worker["ai_advisory"] = ai_advisory
                if ai_advisory.get("status") == "READY":
                    await websocket_manager.broadcast(
                        "ai.forecast.updated",
                        {"worker_id": worker_id, "advisory": ai_advisory},
                    )

                await websocket_manager.broadcast("worker.updated", worker)

                dev_ids = (f"DEV-HLM-{worker_id}", f"HELMET-{worker_id}", worker_id)
                device = next((d for d in simulation_engine.state["devices"] if d["id"] in dev_ids or worker_id in d["id"]), None)
                if device:
                    device.update({
                        "online": True,
                        "hardware_source": True,
                        "last_seen": now,
                        "latest_message": now,
                        "signal": 90,
                    })
                    await websocket_manager.broadcast("device.paired", device)

        elif category == "hazard":
            hazard_id = parts[2]
            hazard = next(
                (h for h in simulation_engine.state["hazards"]
                 if h["id"] == hazard_id or h.get("alias") == hazard_id or h.get("beacon_name") == hazard_id),
                None
            )
            if hazard:
                hazard.update({
                    "online": True,
                    "hardware_source": True,
                    "status": payload.get("operating_status", hazard.get("status", "ACTIVE")),
                    "last_update": now,
                })
                device = next((d for d in simulation_engine.state["devices"] if d["id"] in (f"DEV-BCN-{hazard['id']}", f"HAZARD-{hazard['id']}", f"DEV-BCN-{hazard_id}", f"HAZARD-{hazard_id}")), None)
                if device:
                    device.update({
                        "online": True,
                        "hardware_source": True,
                        "last_seen": now,
                        "latest_message": now,
                    })
                    await websocket_manager.broadcast("device.paired", device)

        elif category == "environment":
            env_id = parts[2]
            dev_ids = (f"DEV-ENV-{env_id}", f"ENV-{env_id}", env_id)
            device = next((d for d in simulation_engine.state["devices"] if d["id"] in dev_ids or env_id in d["id"]), None)
            if device:
                device.update({
                    "online": True,
                    "last_seen": now,
                    "latest_message": now,
                })
                await websocket_manager.broadcast("device.paired", device)

    except Exception as e:
        logger.error("Error processing MQTT message: %s", e)
