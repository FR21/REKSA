import csv
import io
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator

from app.schemas.risk import RiskFeatures, RiskScoreResult
from app.services.risk_engine_service import RiskEngine
from app.services.warning_service import WarningService
from app.services.websocket_service import websocket_manager
from app.simulation.engine import simulation_engine

router = APIRouter()
risk_engine = RiskEngine()
warning_service = WarningService()

SYSTEM_SETTINGS: dict[str, Any] = {
    "moderate_rssi": -70, "high_rssi": -60, "critical_rssi": -45,
    "critical_exposure_duration": 5, "device_offline_timeout": 30,
    "warning_cooldown": 30, "temperature_warning_threshold": 35,
    "humidity_warning_threshold": 80,
}


class NoteInput(BaseModel):
    note: str = Field(min_length=1, max_length=500)

    @field_validator("note")
    @classmethod
    def sanitize(cls, value: str) -> str:
        return value.replace("<", "").replace(">", "").strip()


class AcknowledgeInput(BaseModel):
    supervisor_name: str = Field(default="Raka Wijaya", min_length=2, max_length=120)
    note: str = Field(default="", max_length=500)


class WarningInput(BaseModel):
    worker_id: str
    level: str = "HIGH"
    reason: str = Field(default="Uji peringatan oleh supervisor", max_length=300)
    vibration: bool = True
    buzzer: bool = False
    duration_ms: int = Field(default=3000, ge=500, le=10000)
    confirmed: bool = False


class PairDeviceInput(BaseModel):
    device_id: str = Field(min_length=2, max_length=80)
    device_type: str = Field(pattern="^(SMART_HELMET|HAZARD_NODE|ENVIRONMENT_NODE)$")
    target_id: str = Field(min_length=1, max_length=80)
    assignment: str = Field(default="", max_length=120)

    @field_validator("device_id", "target_id", "assignment")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.replace("<", "").replace(">", "").strip()


class WorkerInput(BaseModel):
    id: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=120)
    role: str = Field(default="Operator", max_length=80)
    area: str = Field(default="Gudang Utama", max_length=80)


def find(items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    item = next((row for row in items if row["id"] == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return item


@router.get("/system/status", tags=["System"])
async def system_status() -> dict[str, Any]:
    return {"status": "OPERATIONAL", "mode": "SIMULATION", "simulation_data": True, "version": "1.0.0", "uptime_percent": 99.7}


@router.get("/system/connections", tags=["System"])
async def connections() -> dict[str, Any]:
    return {"database": "CONNECTED", "mqtt": "SIMULATED", "websocket": "CONNECTED", "connected_clients": len(websocket_manager.connections), "last_checked": datetime.now(UTC).isoformat()}


@router.get("/dashboard/summary", tags=["Dashboard"])
async def dashboard_summary() -> dict[str, Any]:
    state = simulation_engine.state
    workers = state["workers"]
    devices = state["devices"]
    today = datetime.now(UTC).date().isoformat()
    return {
        "active_workers": sum(row["online"] for row in workers),
        "total_workers": len(workers),
        "active_hazards": sum(row["status"] in {"ACTIVE", "MOVING"} for row in state["hazards"]),
        "high_risk_workers": sum(row["risk_level"] == "HIGH" for row in workers),
        "critical_risk_workers": sum(row["risk_level"] == "CRITICAL" for row in workers),
        "near_misses_today": sum(row["timestamp"].startswith(today) for row in state["near_misses"]),
        "average_risk_score": round(sum(row["risk_score"] for row in workers) / len(workers), 1) if workers else 0.0,
        "connected_devices": sum(row["online"] for row in devices),
        "total_devices": len(devices),
        "average_warning_latency": state["history"][-1]["warning_latency"] if state.get("history") else 0.0,
        "simulation_data": True,
    }


@router.get("/dashboard/live", tags=["Dashboard"])
async def dashboard_live() -> dict[str, Any]:
    state = simulation_engine.state
    distribution = {level: sum(worker["risk_level"] == level for worker in state["workers"]) for level in ["SAFE", "MODERATE", "HIGH", "CRITICAL"]}
    return {"workers": state["workers"], "critical_alerts": [w for w in state["workers"] if w["risk_level"] == "CRITICAL"], "risk_distribution": distribution, "hazards": state["hazards"], "simulation_data": True}


@router.get("/dashboard/activity", tags=["Dashboard"])
async def dashboard_activity() -> dict[str, Any]:
    state = simulation_engine.state
    activities = [
        {"id": f"activity-{index}", "type": "NEAR_MISS" if index < 3 else "DEVICE", "message": f"{event['worker_name']} · {event['hazard_name']}" if index < len(state["near_misses"]) else "Sistem aktif", "timestamp": event["timestamp"] if index < len(state["near_misses"]) else datetime.now(UTC).isoformat()}
        for index, event in enumerate(state["near_misses"][:6])
    ]
    return {"items": activities, "simulation_data": True}


@router.get("/workers", tags=["Workers"])
async def workers(search: str = "", risk_level: str | None = None, online: bool | None = None, sort: str = "risk_desc") -> dict[str, Any]:
    rows = simulation_engine.state["workers"].copy()
    if search:
        needle = search.casefold()
        rows = [row for row in rows if needle in row["name"].casefold() or needle in row["id"].casefold()]
    if risk_level:
        rows = [row for row in rows if row["risk_level"] == risk_level.upper()]
    if online is not None:
        rows = [row for row in rows if row["online"] is online]
    rows.sort(key=lambda row: row["risk_score"], reverse=sort != "risk_asc")
    return {"items": rows, "total": len(rows), "simulation_data": True}


@router.post("/workers", tags=["Workers"])
async def create_worker(values: WorkerInput) -> dict[str, Any]:
    exists = any(w["id"] == values.id for w in simulation_engine.state["workers"])
    if exists:
        raise HTTPException(status_code=400, detail="Pekerja dengan ID tersebut sudah terdaftar")
    worker = {
        "id": values.id,
        "name": values.name,
        "role": values.role,
        "area": values.area,
        "online": False,
        "risk_score": 0,
        "risk_level": "SAFE",
        "closest_hazard": "",
        "hazard_name": "-",
        "hazard_type": "-",
        "hazard_status": "-",
        "rssi": 0,
        "smoothed_rssi": 0,
        "proximity": "SAFE",
        "exposure_seconds": 0,
        "movement": "STATIONARY",
        "impact": False,
        "fall_detected": False,
        "impact_g": 1.0,
        "mq135_raw": 0,
        "air_quality_level": "UNKNOWN",
        "gas_alert": False,
        "temperature": 27.0,
        "humidity": 50.0,
        "x": 0.0,
        "y": 0.0,
        "calculation_source": "RULE_BASED_SCORING",
        "dominant_factor": "None",
        "recommended_action": "Pekerja baru terdaftar.",
        "ai_advisory": {
            "status": "AWAITING_LIVE_TELEMETRY",
            "advisory_only": True,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }
    simulation_engine.state["workers"].insert(0, worker)
    await websocket_manager.broadcast("worker.updated", worker)
    return {"worker": worker, "message": "Pekerja berhasil didaftarkan"}


@router.delete("/workers/{worker_id}", tags=["Workers"])
async def delete_worker(worker_id: str) -> dict[str, Any]:
    worker = next((w for w in simulation_engine.state["workers"] if w["id"] == worker_id), None)
    if worker is None:
        raise HTTPException(status_code=404, detail="Pekerja tidak ditemukan")
    
    # Remove worker
    simulation_engine.state["workers"] = [w for w in simulation_engine.state["workers"] if w["id"] != worker_id]
    
    # Clean up associated devices
    devices_to_keep = []
    for dev in simulation_engine.state["devices"]:
        if dev["id"] == f"HELMET-{worker_id}":
            await websocket_manager.broadcast("device.deleted", {"id": dev["id"]})
        elif dev["assignment"] == worker["name"]:
            dev["assignment"] = "-"
            dev["online"] = False
            await websocket_manager.broadcast("device.paired", dev)
            devices_to_keep.append(dev)
        else:
            devices_to_keep.append(dev)
    simulation_engine.state["devices"] = devices_to_keep
    
    # Broadcast deletion
    await websocket_manager.broadcast("worker.deleted", {"id": worker_id})
    return {"message": "Pekerja berhasil dihapus", "id": worker_id}


@router.get("/workers/{worker_id}", tags=["Workers"])
async def worker_detail(worker_id: str) -> dict[str, Any]:
    worker = find(simulation_engine.state["workers"], worker_id)
    worker_events = [event for event in simulation_engine.state["near_misses"] if event["worker_id"] == worker_id]
    factors = [
        {"factor": "Paparan bahaya", "value": min(100, worker["risk_score"] + 10)},
        {"factor": "Near-miss", "value": min(100, len(worker_events) * 22)},
        {"factor": "Risiko aktivitas", "value": 62 if worker["hazard_status"] in {"ACTIVE", "MOVING"} else 20},
        {"factor": "Paparan panas", "value": max(0, (worker["temperature"] - 28) * 12)},
        {"factor": "Kualitas udara", "value": 100 if worker.get("air_quality_level") == "DANGEROUS" else 72 if worker.get("air_quality_level") == "POOR" else 35 if worker.get("air_quality_level") == "MODERATE" else 8},
        {"factor": "Durasi kerja", "value": 54},
        {"factor": "Status benturan", "value": 100 if worker["impact"] else 0},
    ]
    return {**worker, "risk_factors": factors, "near_misses": worker_events, "simulation_data": True}


@router.post("/workers/{worker_id}/mark-safe", tags=["Workers"])
async def mark_worker_safe(worker_id: str) -> dict[str, Any]:
    worker = find(simulation_engine.state["workers"], worker_id)
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
        "exposure_seconds": 0,
        "impact": False,
        "fall_detected": False,
        "impact_g": 1.0,
        "mq135_raw": 0,
        "air_quality_level": "NORMAL",
        "gas_alert": False,
        "dominant_factor": "None",
        "recommended_action": "Kondisi telah ditandai aman oleh supervisor.",
        "last_update": datetime.now(UTC).isoformat(),
    })
    await websocket_manager.broadcast("worker.updated", worker)
    return worker


@router.get("/workers/{worker_id}/risk-history", tags=["Workers"])
async def worker_risk_history(worker_id: str) -> dict[str, Any]:
    find(simulation_engine.state["workers"], worker_id)
    return {"items": [{"date": row["date"], "score": max(5, row["average_risk"] + (int(worker_id[-1]) - 3) * 3)} for row in simulation_engine.state["history"]], "simulation_data": True}


@router.get("/workers/{worker_id}/exposures", tags=["Workers"])
async def worker_exposures(worker_id: str) -> dict[str, Any]:
    worker = find(simulation_engine.state["workers"], worker_id)
    return {"items": [{"hazard": worker["hazard_name"], "duration_minutes": row["exposure_minutes"], "date": row["date"]} for row in simulation_engine.state["history"][-7:]], "simulation_data": True}


@router.get("/workers/{worker_id}/near-misses", tags=["Workers"])
async def worker_near_misses(worker_id: str) -> dict[str, Any]:
    find(simulation_engine.state["workers"], worker_id)
    rows = [event for event in simulation_engine.state["near_misses"] if event["worker_id"] == worker_id]
    return {"items": rows, "total": len(rows), "simulation_data": True}


@router.get("/hazards", tags=["Hazards"])
async def hazards() -> dict[str, Any]:
    workers_list = simulation_engine.state["workers"]
    rows = [{**hazard, "nearby_workers": [worker for worker in workers_list if worker["closest_hazard"] == hazard["id"]], "exposure_count": sum(worker["closest_hazard"] == hazard["id"] for worker in workers_list), "near_miss_count": sum(event["hazard_id"] == hazard["id"] for event in simulation_engine.state["near_misses"])} for hazard in simulation_engine.state["hazards"]]
    return {"items": rows, "total": len(rows), "coordinate_notice": "Koordinat berasal dari simulasi, bukan posisi presisi BLE RSSI.", "simulation_data": True}


@router.get("/hazards/{hazard_id}", tags=["Hazards"])
async def hazard_detail(hazard_id: str) -> dict[str, Any]:
    hazard = find(simulation_engine.state["hazards"], hazard_id)
    nearby = [worker for worker in simulation_engine.state["workers"] if worker["closest_hazard"] == hazard_id]
    return {**hazard, "nearby_workers": nearby, "latest_rssi": [{"worker_id": worker["id"], "rssi": worker["rssi"]} for worker in nearby], "simulation_data": True}


@router.get("/hazards/{hazard_id}/nearby-workers", tags=["Hazards"])
async def nearby_workers(hazard_id: str) -> dict[str, Any]:
    find(simulation_engine.state["hazards"], hazard_id)
    rows = [worker for worker in simulation_engine.state["workers"] if worker["closest_hazard"] == hazard_id]
    return {"items": rows, "total": len(rows)}


@router.get("/near-misses", tags=["Near Misses"])
async def near_misses(search: str = "", risk_level: str | None = None, acknowledged: bool | None = None, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)) -> dict[str, Any]:
    rows = simulation_engine.state["near_misses"].copy()
    if search:
        needle = search.casefold()
        rows = [row for row in rows if needle in f"{row['id']} {row['worker_name']} {row['hazard_name']}".casefold()]
    if risk_level:
        rows = [row for row in rows if row["risk_level"] == risk_level.upper()]
    if acknowledged is not None:
        rows = [row for row in rows if row["acknowledged"] is acknowledged]
    total = len(rows)
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "total": total, "page": page, "page_size": page_size, "simulation_data": True}


@router.get("/near-misses/export", tags=["Near Misses"])
async def export_near_misses() -> Response:
    output = io.StringIO()
    fields = ["id", "timestamp", "worker_id", "worker_name", "hazard_id", "hazard_name", "hazard_type", "proximity", "rssi", "duration", "risk_score", "warning_status", "acknowledged", "note"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(simulation_engine.state["near_misses"])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=reksa-near-miss.csv"})


@router.get("/near-misses/{event_id}", tags=["Near Misses"])
async def near_miss_detail(event_id: str) -> dict[str, Any]:
    return {**find(simulation_engine.state["near_misses"], event_id), "simulation_data": True}


@router.patch("/near-misses/{event_id}/acknowledge", tags=["Near Misses"])
async def acknowledge(event_id: str, values: AcknowledgeInput) -> dict[str, Any]:
    event = find(simulation_engine.state["near_misses"], event_id)
    event.update({"acknowledged": True, "acknowledged_by": values.supervisor_name, "acknowledged_at": datetime.now(UTC).isoformat()})
    if values.note:
        event["note"] = values.note.replace("<", "").replace(">", "")[:500]
    await websocket_manager.broadcast("near_miss.acknowledged", event)
    return event


@router.patch("/near-misses/{event_id}/note", tags=["Near Misses"])
async def add_note(event_id: str, values: NoteInput) -> dict[str, Any]:
    event = find(simulation_engine.state["near_misses"], event_id)
    event["note"] = values.note
    return event


@router.get("/devices", tags=["Devices"])
async def devices(device_type: str | None = None, online: bool | None = None) -> dict[str, Any]:
    rows = simulation_engine.state["devices"].copy()
    if device_type:
        rows = [row for row in rows if row["type"] == device_type]
    if online is not None:
        rows = [row for row in rows if row["online"] is online]
    return {"items": rows, "total": len(rows), "online": sum(row["online"] for row in rows), "simulation_data": True}


@router.post("/devices/pair", tags=["Devices"])
async def pair_device(values: PairDeviceInput) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    assignment = values.assignment
    topic_target = values.target_id
    if values.device_type == "SMART_HELMET":
        worker = find(simulation_engine.state["workers"], values.target_id)
        assignment = assignment or worker["name"]
        topic = f"REKSA/helmet/{worker['id']}/sensor"
    elif values.device_type == "HAZARD_NODE":
        hazard = next((h for h in simulation_engine.state["hazards"] if h["id"] == values.target_id), None)
        if hazard is None:
            # Create new hazard on the fly
            hazard = {
                "id": values.target_id,
                "name": assignment or f"Hazard {values.target_id}",
                "type": "FORKLIFT",
                "status": "ACTIVE",
                "area": "Gudang Utama",
                "x": 0.0,
                "y": 0.0,
                "online": False,
                "last_update": now
            }
            simulation_engine.state["hazards"].append(hazard)
            assignment = hazard["name"]
        else:
            assignment = assignment or hazard["name"]
            if values.assignment:
                hazard["name"] = assignment
                for worker in simulation_engine.state["workers"]:
                    if worker.get("closest_hazard") == hazard["id"]:
                        worker["hazard_name"] = assignment
                        await websocket_manager.broadcast("worker.updated", worker)
        topic = f"REKSA/hazard/{hazard['id']}/beacon"
    else:
        assignment = assignment or values.target_id
        topic_target = values.target_id.replace(" ", "-").upper()
        topic = f"REKSA/environment/{topic_target}/data"

    device = next((row for row in simulation_engine.state["devices"] if row["id"] == values.device_id), None)
    if device is None:
        device = {
            "id": values.device_id,
            "type": values.device_type,
            "assignment": assignment,
            "online": False,
            "last_seen": now,
            "firmware": "unknown",
            "signal": 0,
            "topic": topic,
            "latest_message": now,
        }
        simulation_engine.state["devices"].insert(0, device)
    else:
        device.update({"type": values.device_type, "assignment": assignment, "topic": topic, "last_seen": now})

    await websocket_manager.broadcast("device.paired", device)
    return {"device": device, "message": "Device berhasil dipairing"}


@router.get("/devices/{device_id}", tags=["Devices"])
async def device_detail(device_id: str) -> dict[str, Any]:
    return {**find(simulation_engine.state["devices"], device_id), "offline_timeout_seconds": SYSTEM_SETTINGS["device_offline_timeout"], "simulation_data": True}


@router.delete("/devices/{device_id}", tags=["Devices"])
async def delete_device(device_id: str) -> dict[str, Any]:
    device = next((row for row in simulation_engine.state["devices"] if row["id"] == device_id), None)
    if device is None:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")
    
    simulation_engine.state["devices"] = [row for row in simulation_engine.state["devices"] if row["id"] != device_id]
    
    # If device was a hazard node, remove the hazard from the active hazards list
    if device["type"] == "HAZARD_NODE" or device_id.startswith("HAZARD-"):
        hazard_id = device_id.replace("HAZARD-", "")
        simulation_engine.state["hazards"] = [h for h in simulation_engine.state["hazards"] if h["id"] != hazard_id]
        
    # If device was assigned to a worker, update their status to offline & safe
    if device["type"] == "SMART_HELMET":
        worker_id = None
        parts = device["topic"].split("/")
        if len(parts) >= 3 and parts[1] == "helmet":
            worker_id = parts[2]
        
        for w in simulation_engine.state["workers"]:
            if (worker_id and w["id"] == worker_id) or w["name"] == device["assignment"]:
                w["online"] = False
                w["risk_score"] = 0
                w["risk_level"] = "SAFE"
                await websocket_manager.broadcast("worker.updated", w)
                
    await websocket_manager.broadcast("device.deleted", {"id": device_id})
    return {"message": "Device berhasil dihapus", "id": device_id}


@router.get("/devices/{device_id}/history", tags=["Devices"])
async def device_history(device_id: str) -> dict[str, Any]:
    find(simulation_engine.state["devices"], device_id)
    return {"items": [{"date": row["date"], "uptime": row["uptime"]} for row in simulation_engine.state["history"]]}


def filtered_history(period: str) -> list[dict[str, Any]]:
    history = simulation_engine.state["history"]
    return history[-1:] if period == "today" else history[-7:] if period == "7d" else history


@router.get("/analytics/risk-trend", tags=["Analytics"])
async def risk_trend(period: str = "7d") -> dict[str, Any]:
    return {"items": filtered_history(period), "simulation_data": True}


@router.get("/analytics/near-miss-trend", tags=["Analytics"])
async def near_miss_trend(period: str = "7d") -> dict[str, Any]:
    history = filtered_history(period)
    by_type = [{"type": hazard_type, "count": sum(event["hazard_type"] == hazard_type for event in simulation_engine.state["near_misses"])} for hazard_type in ["FORKLIFT", "GRINDING", "LASER"]]
    return {"items": history, "by_type": by_type, "simulation_data": True}


@router.get("/analytics/exposure", tags=["Analytics"])
async def exposure(period: str = "7d") -> dict[str, Any]:
    return {"items": filtered_history(period), "by_hazard": [{"name": hazard["name"], "minutes": 18 + index * 13, "frequency": 4 + index * 2} for index, hazard in enumerate(simulation_engine.state["hazards"])], "simulation_data": True}


@router.get("/analytics/device-uptime", tags=["Analytics"])
async def device_uptime(period: str = "7d") -> dict[str, Any]:
    return {"items": filtered_history(period), "average_uptime": 98.2, "simulation_data": True}


@router.get("/analytics/environment", tags=["Analytics"])
async def environment(period: str = "7d") -> dict[str, Any]:
    return {"items": filtered_history(period), "simulation_data": True}


@router.post("/risk/score", response_model=RiskScoreResult, tags=["Risk"])
async def score_risk(features: RiskFeatures) -> RiskScoreResult:
    return risk_engine.score(features)


@router.get("/settings", tags=["Settings"])
async def get_settings() -> dict[str, Any]:
    return {"values": SYSTEM_SETTINGS, "simulation_data": True}


@router.patch("/settings", tags=["Settings"])
async def update_settings(values: dict[str, Any]) -> dict[str, Any]:
    unknown = set(values) - set(SYSTEM_SETTINGS) - {"confirmed"}
    if unknown:
        raise HTTPException(status_code=422, detail=f"Pengaturan tidak dikenal: {', '.join(sorted(unknown))}")
    if not values.get("confirmed"):
        raise HTTPException(status_code=400, detail="Konfirmasi diperlukan untuk mengubah threshold keselamatan")
    updates = {key: value for key, value in values.items() if key in SYSTEM_SETTINGS}
    if {"moderate_rssi", "high_rssi", "critical_rssi"} & set(updates):
        merged = {**SYSTEM_SETTINGS, **updates}
        if not merged["moderate_rssi"] < merged["high_rssi"] < merged["critical_rssi"]:
            raise HTTPException(status_code=422, detail="Threshold RSSI harus berurutan: moderate < high < critical")
    SYSTEM_SETTINGS.update(updates)
    return {"values": SYSTEM_SETTINGS, "message": "Pengaturan tersimpan"}


@router.post("/simulation/reset", tags=["Simulation"])
async def simulation_reset() -> dict[str, Any]:
    await simulation_engine.reset()
    return simulation_engine.get_status()


@router.post("/warnings/test", tags=["Warnings"])
@router.post("/warnings/send", tags=["Warnings"])
async def send_warning(values: WarningInput) -> dict[str, Any]:
    find(simulation_engine.state["workers"], values.worker_id)
    if values.buzzer and not values.confirmed:
        raise HTTPException(status_code=400, detail="Konfirmasi wajib sebelum mengaktifkan buzzer")
    warning = warning_service.create(values.worker_id, values.level.upper(), values.reason, buzzer=values.buzzer, vibration=values.vibration, duration_ms=values.duration_ms)
    simulation_engine.state["warnings"].insert(0, warning)
    
    # Publish warning via MQTT
    from app.main import mqtt_service
    mqtt_service.publish(warning["mqtt_topic"], warning)
    
    await websocket_manager.broadcast("warning.created", warning)
    return warning


@router.get("/warnings", tags=["Warnings"])
async def warnings() -> dict[str, Any]:
    return {"items": simulation_engine.state["warnings"], "total": len(simulation_engine.state["warnings"]), "simulation_data": True}
