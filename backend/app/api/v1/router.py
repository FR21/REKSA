import base64
import csv
import io
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.schemas.risk import RiskFeatures, RiskScoreResult
from app.services.db_service import db_service
from app.services.risk_engine_service import RiskEngine
from app.services.warning_service import WarningService
from app.services.websocket_service import websocket_manager
from app.simulation.engine import simulation_engine

router = APIRouter()
risk_engine = RiskEngine()
warning_service = WarningService()

SYSTEM_SETTINGS: dict[str, Any] = {
    "mobile_moderate_rssi": -86, "mobile_high_rssi": -78, "mobile_critical_rssi": -70,
    "stationary_moderate_rssi": -82, "stationary_high_rssi": -74, "stationary_critical_rssi": -65,
    "moderate_rssi": -86, "high_rssi": -78, "critical_rssi": -70,
    "critical_exposure_duration": 5, "device_offline_timeout": 30,
    "warning_cooldown": 30, "temperature_warning_threshold": 35,
    "humidity_warning_threshold": 80,
    # Threshold Helm v1 (Sensory K3: DHT22, MQ135, MPU6050)
    "heat_warning_c": 30.0,
    "heat_danger_c": 35.0,
    "mq135_normal_max": 1200,
    "mq135_moderate_max": 1800,
    "mq135_poor_max": 2500,
    "impact_g_warning": 2.5,
    "impact_g_critical": 3.5,
    "fall_freefall_g": 0.45,
}

CURRENT_USER_PROFILE: dict[str, str] = {
    "name": "Raka Wijaya",
    "role": "Supervisor K3",
}


def calculate_initials(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    if len(parts) > 1:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    return (name.strip()[:2] or "US").upper()


class ProfileInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    role: str = Field(default="Supervisor K3", min_length=2, max_length=80)

    @field_validator("name", "role")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.replace("<", "").replace(">", "").strip()


class NoteInput(BaseModel):
    note: str = Field(min_length=1, max_length=500)

    @field_validator("note")
    @classmethod
    def sanitize(cls, value: str) -> str:
        return value.replace("<", "").replace(">", "").strip()


class AcknowledgeInput(BaseModel):
    supervisor_name: str = Field(default="", max_length=120)
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
    device_type: str = Field(pattern="^(SMART_HELMET|HAZARD_NODE|HAZARD_MOBILE|HAZARD_STATIONARY|ENVIRONMENT_NODE)$")
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


class HazardCreateInput(BaseModel):
    id: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=120)
    type: str = Field(default="FORKLIFT", max_length=40)
    category: str = Field(default="MOBILE", pattern="^(MOBILE|STATIONARY)$")
    area: str = Field(default="Gudang Utama", max_length=80)
    alias: str = Field(default="", max_length=20)
    beacon_name: str = Field(default="", max_length=40)


def find(items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    item = next(
        (row for row in items
         if row.get("id") == item_id or row.get("alias") == item_id or row.get("beacon_name") == item_id),
        None
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return item


@router.get("/system/status", tags=["System"])
async def system_status() -> dict[str, Any]:
    return {"status": "OPERATIONAL", "mode": "SIMULATION", "simulation_data": True, "version": "1.0.0", "uptime_percent": 99.7}


@router.get("/system/connections", tags=["System"])
async def connections() -> dict[str, Any]:
    return {"database": "CONNECTED", "mqtt": "SIMULATED", "websocket": "CONNECTED", "connected_clients": len(websocket_manager.connections), "last_checked": datetime.now(UTC).isoformat()}


def sync_today_history() -> None:
    state = simulation_engine.state
    history = state.setdefault("history", [])
    today = datetime.now(UTC).date().isoformat()
    workers = state.get("workers", [])
    active_workers = [w for w in workers if w.get("online", False)]
    avg_risk = round(sum(w["risk_score"] for w in active_workers) / len(active_workers), 1) if active_workers else 0.0
    near_misses_today = sum(row["timestamp"].startswith(today) for row in state.get("near_misses", []))
    devices = state.get("devices", [])
    uptime = round((sum(d.get("online", False) for d in devices) / max(1, len(devices))) * 100, 1)

    if not history:
        history.append({
            "date": today,
            "average_risk": round(avg_risk),
            "near_misses": near_misses_today,
            "exposure_minutes": sum(w.get("exposure_seconds", 0) for w in active_workers) // 60,
            "temperature": round(sum(w.get("temperature", 29.5) for w in active_workers) / max(1, len(active_workers)), 1),
            "humidity": round(sum(w.get("humidity", 65.0) for w in active_workers) / max(1, len(active_workers)), 1),
            "uptime": uptime,
            "warning_latency": 142,
        })
    else:
        if history[-1].get("date") != today:
            history.append({
                "date": today,
                "average_risk": round(avg_risk),
                "near_misses": near_misses_today,
                "exposure_minutes": sum(w.get("exposure_seconds", 0) for w in active_workers) // 60,
                "temperature": round(sum(w.get("temperature", 29.5) for w in active_workers) / max(1, len(active_workers)), 1),
                "humidity": round(sum(w.get("humidity", 65.0) for w in active_workers) / max(1, len(active_workers)), 1),
                "uptime": uptime,
                "warning_latency": history[-1].get("warning_latency", 142),
            })
        else:
            history[-1]["average_risk"] = round(avg_risk)
            history[-1]["near_misses"] = near_misses_today
            history[-1]["uptime"] = uptime
            history[-1]["exposure_minutes"] = sum(w.get("exposure_seconds", 0) for w in active_workers) // 60


@router.get("/dashboard/summary", tags=["Dashboard"])
async def dashboard_summary() -> dict[str, Any]:
    sync_today_history()
    state = simulation_engine.state
    workers = state["workers"]
    active_workers = [w for w in workers if w.get("online", False)]
    devices = state["devices"]
    today = datetime.now(UTC).date().isoformat()
    avg_risk = round(sum(w["risk_score"] for w in active_workers) / len(active_workers), 1) if active_workers else 0.0
    return {
        "active_workers": len(active_workers),
        "total_workers": len(workers),
        "active_hazards": sum(row["status"] in {"ACTIVE", "MOVING"} for row in state["hazards"]),
        "high_risk_workers": sum(row["risk_level"] == "HIGH" for row in active_workers),
        "critical_risk_workers": sum(row["risk_level"] == "CRITICAL" for row in active_workers),
        "near_misses_today": sum(row["timestamp"].startswith(today) for row in state["near_misses"]),
        "average_risk_score": avg_risk,
        "connected_devices": sum(row["online"] for row in devices),
        "total_devices": len(devices),
        "average_warning_latency": state["history"][-1]["warning_latency"] if state.get("history") else 142,
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
    items: list[dict[str, Any]] = []

    for act in state.get("activities", []):
        items.append({
            "id": act["id"],
            "type": act.get("type", "DEVICE"),
            "message": act["message"],
            "timestamp": act["timestamp"],
        })

    for nm in state.get("near_misses", [])[:10]:
        items.append({
            "id": f"act-nm-{nm['id']}",
            "type": "NEAR_MISS",
            "message": f"{nm['worker_name']} ({nm['worker_id']}) mendekati {nm['hazard_name']} · RSSI {nm.get('rssi', -45)} dBm",
            "timestamp": nm["timestamp"],
        })

    for w in state.get("warnings", [])[:10]:
        items.append({
            "id": f"act-wrn-{w.get('warning_id', '')}",
            "type": "WARNING",
            "message": f"Sinyal buzzer dikirim ke pekerja {w.get('worker_id')} · {w.get('reason')}",
            "timestamp": w.get("timestamp", datetime.now(UTC).isoformat()),
        })

    for v in state.get("voice_transmissions", [])[:10]:
        items.append({
            "id": f"act-voc-{v.get('id', '')}",
            "type": "VOICE",
            "message": f"Instruksi suara ke {v.get('target', 'All')}: \"{v.get('text', '')[:45]}\"",
            "timestamp": v.get("timestamp", datetime.now(UTC).isoformat()),
        })

    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    seen_ids = set()
    deduped = []
    for item in items:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            deduped.append(item)
        if len(deduped) >= 15:
            break

    return {"items": deduped, "simulation_data": True}


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
        "online": True,
        "risk_score": 15,
        "risk_level": "SAFE",
        "closest_hazard": None,
        "hazard_name": "-",
        "hazard_type": "-",
        "hazard_category": "NONE",
        "hazard_status": "INACTIVE",
        "rssi": -90,
        "smoothed_rssi": -90,
        "proximity": "SAFE",
        "exposure_seconds": 0,
        "movement": "DIAM",
        "impact": False,
        "fall_detected": False,
        "impact_g": 1.0,
        "mq135_raw": 420,
        "air_quality_level": "NORMAL",
        "gas_alert": False,
        "temperature": 28.5,
        "humidity": 65.0,
        "calculation_source": "RULE_BASED_SCORING",
        "dominant_factor": "None",
        "recommended_action": "Pekerja baru terdaftar. Helm terpasang & siap beroperasi.",
        "last_update": datetime.now(UTC).isoformat(),
        "ai_advisory": {
            "status": "AWAITING_LIVE_TELEMETRY",
            "advisory_only": True,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }
    simulation_engine.state["workers"].insert(0, worker)

    # Auto-provision paired Smart Helmet device for the new worker
    helmet_dev_id = f"DEV-HLM-{values.id}"
    dev_exists = any(d["id"] == helmet_dev_id for d in simulation_engine.state["devices"])
    if not dev_exists:
        helmet_dev = {
            "id": helmet_dev_id,
            "type": "SMART_HELMET",
            "assignment": values.name,
            "online": True,
            "last_seen": datetime.now(UTC).isoformat(),
            "firmware": "0.2.0",
            "signal": 85,
            "topic": f"REKSA/helmet/{values.id}/sensor",
            "latest_message": datetime.now(UTC).isoformat(),
        }
        simulation_engine.state["devices"].append(helmet_dev)
        await websocket_manager.broadcast("device.paired", helmet_dev)

    sync_today_history()
    await websocket_manager.broadcast("worker.updated", worker)
    return {"worker": worker, "message": "Pekerja & Smart Helmet berhasil didaftarkan"}


@router.delete("/workers/{worker_id}", tags=["Workers"])
async def delete_worker(worker_id: str) -> dict[str, Any]:
    worker = next((w for w in simulation_engine.state["workers"] if w["id"] == worker_id), None)
    if worker is None:
        raise HTTPException(status_code=404, detail="Pekerja tidak ditemukan")
    
    simulation_engine.state["workers"] = [w for w in simulation_engine.state["workers"] if w["id"] != worker_id]

    devices_to_keep = []
    for dev in simulation_engine.state["devices"]:
        if dev["id"] in (f"DEV-HLM-{worker_id}", f"HELMET-{worker_id}"):
            await websocket_manager.broadcast("device.deleted", {"id": dev["id"]})
        elif dev["assignment"] == worker["name"]:
            dev["assignment"] = "-"
            dev["online"] = False
            await websocket_manager.broadcast("device.paired", dev)
            devices_to_keep.append(dev)
        else:
            devices_to_keep.append(dev)
    simulation_engine.state["devices"] = devices_to_keep

    sync_today_history()
    await websocket_manager.broadcast("worker.deleted", {"id": worker_id})
    return {"message": "Pekerja berhasil dihapus", "id": worker_id}


@router.put("/workers/{worker_id}", tags=["Workers"])
async def update_worker(worker_id: str, values: WorkerInput) -> dict[str, Any]:
    worker = next((w for w in simulation_engine.state["workers"] if w["id"] == worker_id), None)
    if worker is None:
        raise HTTPException(status_code=404, detail="Pekerja tidak ditemukan")

    worker["name"] = values.name
    worker["role"] = values.role
    worker["area"] = values.area
    worker["last_update"] = datetime.now(UTC).isoformat()

    # Also update device assignment if a device is assigned to this worker
    for dev in simulation_engine.state["devices"]:
        if dev["id"] in (f"DEV-HLM-{worker_id}", f"HELMET-{worker_id}"):
            dev["assignment"] = values.name
            await websocket_manager.broadcast("device.paired", dev)

    sync_today_history()
    await websocket_manager.broadcast("worker.updated", worker)
    return {"worker": worker, "message": "Data pekerja berhasil diperbarui"}


@router.get("/workers/{worker_id}", tags=["Workers"])
async def worker_detail(worker_id: str) -> dict[str, Any]:
    worker = find(simulation_engine.state["workers"], worker_id)
    
    # Query persistent near miss events from PostgreSQL database first
    worker_events: list[dict[str, Any]] = []
    try:
        from app.database.session import SessionLocal
        from app.models.entities import Hazard as DBHazard
        from app.models.entities import NearMissEvent
        from app.models.entities import Worker as DBWorker
        with SessionLocal() as db:
            db_worker = db.scalar(select(DBWorker).where(DBWorker.worker_code == worker_id))
            if db_worker:
                db_events = (
                    db.query(NearMissEvent, DBHazard)
                    .join(DBHazard, NearMissEvent.hazard_id == DBHazard.id)
                    .filter(NearMissEvent.worker_id == db_worker.id)
                    .order_by(NearMissEvent.occurred_at.desc())
                    .all()
                )
                for nm, h in db_events:
                    worker_events.append({
                        "id": nm.event_code,
                        "timestamp": nm.occurred_at.isoformat(),
                        "worker_id": worker_id,
                        "worker_name": worker.get("name", db_worker.name),
                        "hazard_id": h.hazard_code,
                        "hazard_name": h.name,
                        "hazard_type": h.hazard_type,
                        "proximity": "CRITICAL" if nm.risk_score >= 75 else "HIGH",
                        "rssi": nm.maximum_rssi,
                        "duration": float(nm.critical_duration) if nm.critical_duration is not None else 5.0,
                        "hazard_status": nm.hazard_status,
                        "risk_score": nm.risk_score,
                        "risk_level": "CRITICAL" if nm.risk_score >= 75 else "HIGH",
                        "warning_status": nm.warning_status,
                        "acknowledged": nm.acknowledged,
                        "note": nm.supervisor_note or "",
                    })
    except Exception as exc:
        logging.getLogger(__name__).debug("Database query fallback for worker %s: %s", worker_id, exc)

    if not worker_events:
        worker_events = [event for event in simulation_engine.state.get("near_misses", []) if event.get("worker_id") == worker_id]
    
    # Calculate live sensor-driven risk breakdown
    has_hazard = worker.get("closest_hazard") is not None and worker.get("hazard_name") != "-"
    proximity_factor = min(100, max(10, int((worker.get("smoothed_rssi", -100) + 95) * 2.2))) if has_hazard else 0
    activity_factor = 75 if worker.get("hazard_status") in {"ACTIVE", "MOVING"} else 30 if worker.get("movement") == "BERGERAK" else 10
    heat_factor = max(0, min(100, int((worker.get("temperature", 28.0) - 26.0) * 12.5)))
    air_factor = 100 if worker.get("air_quality_level") == "DANGEROUS" else 70 if worker.get("air_quality_level") == "POOR" else 35 if worker.get("air_quality_level") == "MODERATE" else max(5, int((worker.get("mq135_raw", 350) / 1200) * 30))
    exposure_factor = min(100, max(15, int((worker.get("exposure_seconds", 60) / 360) * 85)))
    impact_factor = 100 if worker.get("fall_detected") else 90 if worker.get("impact") else max(0, int((worker.get("impact_g", 1.0) - 1.0) * 45))

    factors = [
        {"factor": "Paparan bahaya", "value": proximity_factor},
        {"factor": "Near-miss", "value": min(100, len(worker_events) * 25)},
        {"factor": "Risiko aktivitas", "value": activity_factor},
        {"factor": "Paparan panas", "value": heat_factor},
        {"factor": "Kualitas udara", "value": air_factor},
        {"factor": "Durasi kerja", "value": exposure_factor},
        {"factor": "Status benturan", "value": impact_factor},
    ]
    return {**worker, "risk_factors": factors, "near_misses": worker_events, "simulation_data": True}


@router.post("/workers/{worker_id}/mark-safe", tags=["Workers"])
async def mark_worker_safe(worker_id: str) -> dict[str, Any]:
    worker = find(simulation_engine.state["workers"], worker_id)
    now = datetime.now(UTC)
    now_str = now.isoformat()

    prev_level = worker.get("risk_level", "SAFE")
    prev_score = worker.get("risk_score", 10)
    prev_hazard_id = worker.get("closest_hazard")
    prev_hazard_name = worker.get("hazard_name")

    if prev_level in ("CRITICAL", "HIGH") or prev_score >= 50 or (prev_hazard_id and prev_hazard_id != "-"):
        nm_event = {
            "id": f"NM-{now.strftime('%H%M%S')}-{worker_id}",
            "timestamp": now_str,
            "worker_id": worker_id,
            "worker_name": worker.get("name", worker_id),
            "hazard_id": prev_hazard_id or "HAZARD-01",
            "hazard_name": prev_hazard_name if prev_hazard_name and prev_hazard_name != "-" else "Area Bahaya Terdekat",
            "hazard_type": worker.get("hazard_type") if worker.get("hazard_type") != "-" else "FORKLIFT",
            "proximity": worker.get("proximity") if worker.get("proximity") in ("CRITICAL", "HIGH") else "CRITICAL",
            "rssi": worker.get("rssi", -68) if worker.get("rssi", -100) > -100 else -68,
            "duration": max(5.0, float(worker.get("exposure_seconds", 5.0))),
            "hazard_status": worker.get("hazard_status") if worker.get("hazard_status") != "INACTIVE" else "MOVING",
            "risk_score": max(prev_score, 78),
            "risk_level": prev_level if prev_level in ("CRITICAL", "HIGH") else "CRITICAL",
            "warning_status": "DELIVERED",
            "acknowledged": True,
            "acknowledged_by": "Supervisor Lapangan",
            "acknowledged_at": now_str,
            "note": "Pekerja telah dievakuasi ke zona aman dan diverifikasi oleh supervisor di lapangan.",
        }
        simulation_engine.state.setdefault("near_misses", []).insert(0, nm_event)
        await db_service.persist_near_miss(nm_event)
        await websocket_manager.broadcast("near_miss.created", nm_event)

    worker.update({
        "closest_hazard": prev_hazard_id,
        "hazard_name": prev_hazard_name if prev_hazard_name and prev_hazard_name != "-" else "Zona Aman",
        "hazard_type": worker.get("hazard_type", "-"),
        "hazard_status": "IDLE",
        "rssi": -88,
        "smoothed_rssi": -88,
        "proximity": "RECOVERY",
        "risk_level": "RECOVERY",
        "risk_score": 18,
        "exposure_seconds": 0,
        "impact": False,
        "fall_detected": False,
        "impact_g": 1.0,
        "mq135_raw": 420,
        "air_quality_level": "NORMAL",
        "gas_alert": False,
        "dominant_factor": "Mode Pemulihan (Recovery)",
        "recommended_action": "Pekerja dalam Mode Pemulihan (Recovery). Kondisi aman bertahan, alarm dihentikan, event ditutup dan durasi telah dihitung.",
        "recovery": {
            "active": True,
            "alarm_silenced": True,
            "event_closed": True,
            "note": "Kondisi aman bertahan setelah keluar zona bahaya. Alarm dihentikan, event ditutup, dan durasi dihitung.",
        },
        "last_update": now_str,
    })
    simulation_engine.state.setdefault("activities", []).insert(0, {
        "id": f"act-safe-{worker_id}-{int(now.timestamp())}",
        "type": "SAFE",
        "message": f"Pekerja {worker['name']} ({worker_id}) ditandai aman oleh supervisor",
        "timestamp": now_str,
    })
    sync_today_history()
    await websocket_manager.broadcast("worker.updated", worker)
    return worker


@router.get("/workers/{worker_id}/risk-history", tags=["Workers"])
async def worker_risk_history(worker_id: str) -> dict[str, Any]:
    worker = find(simulation_engine.state["workers"], worker_id)
    current_score = worker.get("risk_score", 10)

    # Query persistent RiskAssessment records from PostgreSQL database
    try:
        from app.database.session import SessionLocal
        from app.models.entities import RiskAssessment as DBRiskAssessment
        from app.models.entities import Worker as DBWorker
        with SessionLocal() as db:
            db_worker = db.scalar(select(DBWorker).where(DBWorker.worker_code == worker_id))
            if db_worker:
                db_assessments = (
                    db.scalars(
                        select(DBRiskAssessment)
                        .where(DBRiskAssessment.worker_id == db_worker.id)
                        .order_by(DBRiskAssessment.assessed_at.asc())
                    ).all()
                )
                if db_assessments:
                    items = [
                        {
                            "date": a.assessed_at.strftime("%Y-%m-%d"),
                            "score": a.risk_score,
                        }
                        for a in db_assessments
                    ]
                    # Anchor tail with the live current risk score
                    if items:
                        items[-1]["score"] = current_score
                    return {"items": items, "source": "DATABASE"}
    except Exception as exc:
        logging.getLogger(__name__).debug("Risk history DB fallback for %s: %s", worker_id, exc)

    history = simulation_engine.state.get("history", [])
    worker_events = [e for e in simulation_engine.state.get("near_misses", []) if e.get("worker_id") == worker_id]
    nm_dates = {e.get("timestamp", "")[:10] for e in worker_events}
    
    items = []
    total = len(history)
    for idx, row in enumerate(history):
        date = row.get("date", "")
        if idx == total - 1:
            score = current_score
        else:
            diff = row.get("average_risk", 35) - 35
            base = max(5, min(95, current_score + diff))
            if date in nm_dates:
                base = max(base, 78)
            score = base
        items.append({"date": date, "score": score})
    return {"items": items, "simulation_data": True}


@router.get("/workers/{worker_id}/exposures", tags=["Workers"])
async def worker_exposures(worker_id: str) -> dict[str, Any]:
    worker = find(simulation_engine.state["workers"], worker_id)
    worker_events = [e for e in simulation_engine.state.get("near_misses", []) if e.get("worker_id") == worker_id]
    history = simulation_engine.state.get("history", [])[-7:]
    
    known_hazards = [e.get("hazard_name") for e in worker_events if e.get("hazard_name")]
    if worker.get("hazard_name") and worker["hazard_name"] != "-":
        known_hazards.insert(0, worker["hazard_name"])
    if not known_hazards:
        known_hazards = ["Forklift Alpha", "Gerinda Stasiun 1"]

    items = []
    for idx, row in enumerate(history):
        hz = known_hazards[idx % len(known_hazards)]
        duration = max(5, row.get("exposure_minutes", 20) // 2 + (idx * 3))
        items.append({
            "hazard": hz,
            "duration_minutes": duration,
            "date": row.get("date", ""),
        })
    return {"items": items, "simulation_data": True}


@router.get("/workers/{worker_id}/near-misses", tags=["Workers"])
async def worker_near_misses(worker_id: str) -> dict[str, Any]:
    find(simulation_engine.state["workers"], worker_id)
    rows = [event for event in simulation_engine.state["near_misses"] if event["worker_id"] == worker_id]
    return {"items": rows, "total": len(rows), "simulation_data": True}


@router.get("/hazards", tags=["Hazards"])
async def hazards() -> dict[str, Any]:
    workers_list = simulation_engine.state["workers"]
    rows = [{**hazard, "nearby_workers": [worker for worker in workers_list if worker["closest_hazard"] in (hazard["id"], hazard.get("alias"))], "exposure_count": sum(worker["closest_hazard"] in (hazard["id"], hazard.get("alias")) for worker in workers_list), "near_miss_count": sum(event["hazard_id"] in (hazard["id"], hazard.get("alias")) for event in simulation_engine.state["near_misses"])} for hazard in simulation_engine.state["hazards"]]
    return {"items": rows, "total": len(rows), "coordinate_notice": "Koordinat berasal dari simulasi, bukan posisi presisi BLE RSSI.", "simulation_data": True}


@router.post("/hazards", tags=["Hazards"])
async def create_hazard(values: HazardCreateInput) -> dict[str, Any]:
    existing = next(
        (h for h in simulation_engine.state["hazards"]
         if h["id"] == values.id or (values.alias and h.get("alias") == values.alias)),
        None
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Hazard dengan ID {values.id} sudah terdaftar")

    type_code_map = {
        "FORKLIFT": "FLK",
        "CONTAINER_CRANE": "CNT",
        "AGV": "AGV",
        "TRUCK": "TRK",
        "CRANE": "CRN",
        "LASER": "LSR",
        "GRINDING": "GRD",
        "PRESS": "PRS",
        "CNC": "CNC",
        "ROBOT": "ROB",
        "MACHINERY": "MCN",
    }
    if "-" in values.id:
        parts = values.id.split("-")
        code = parts[1].upper() if len(parts) >= 2 and len(parts[1]) == 3 else type_code_map.get(values.type.upper(), values.type[:3].upper())
        cat_code = parts[0].upper() if len(parts) >= 1 and parts[0].upper() in ("M", "S") else ("M" if values.category == "MOBILE" else "S")
        num_code = parts[2] if len(parts) >= 3 and parts[2].isdigit() else (values.id[-2:] if values.id[-2:].isdigit() else "01")
    else:
        cat_code = "M" if values.category == "MOBILE" else "S"
        code = type_code_map.get(values.type.upper(), values.type[:3].upper())
        num_code = values.id[-2:] if values.id[-2:].isdigit() else "01"

    now = datetime.now(UTC).isoformat()
    beacon = values.beacon_name or f"RK_{cat_code}_{code}{num_code}"
    new_hazard = {
        "id": values.id,
        "name": values.name,
        "type": values.type,
        "category": values.category,
        "status": "ACTIVE",
        "area": values.area,
        "online": False,
        "last_update": now,
        "alias": values.alias,
        "beacon_name": beacon,
    }
    simulation_engine.state["hazards"].append(new_hazard)

    dev_id = f"DEV-BCN-{values.id}"
    dev_type = "HAZARD_MOBILE" if values.category == "MOBILE" else "HAZARD_STATIONARY"
    if not any(d["id"] == dev_id for d in simulation_engine.state["devices"]):
        device = {
            "id": dev_id,
            "type": dev_type,
            "assignment": values.name,
            "online": False,
            "last_seen": now,
            "firmware": "0.2.0",
            "signal": 0,
            "topic": f"REKSA/hazard/{values.id}/beacon",
            "latest_message": now,
        }
        simulation_engine.state["devices"].insert(0, device)
        await websocket_manager.broadcast("device.paired", device)

    await websocket_manager.broadcast("hazard.created", new_hazard)
    return {"hazard": new_hazard, "message": "Hazard berhasil didaftarkan"}


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
    simulation_engine.state.setdefault("activities", []).insert(0, {
        "id": f"act-ack-{event_id}-{int(datetime.now(UTC).timestamp())}",
        "type": "INVESTIGATION",
        "message": f"Investigasi {event_id} diverifikasi oleh {values.supervisor_name} ({event['worker_name']})",
        "timestamp": datetime.now(UTC).isoformat(),
    })
    sync_today_history()
    await websocket_manager.broadcast("near_miss.acknowledged", event)
    await db_service.persist_acknowledgement(event_id, values.supervisor_name, event.get("note", ""))
    return event


@router.patch("/near-misses/{event_id}/note", tags=["Near Misses"])
async def add_note(event_id: str, values: NoteInput) -> dict[str, Any]:
    event = find(simulation_engine.state["near_misses"], event_id)
    event["note"] = values.note
    await db_service.persist_near_miss_note(event_id, values.note)
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
    elif values.device_type in ("HAZARD_NODE", "HAZARD_MOBILE", "HAZARD_STATIONARY"):
        hazard = next(
            (h for h in simulation_engine.state["hazards"]
             if h["id"] == values.target_id or h.get("alias") == values.target_id or h.get("beacon_name") == values.target_id),
            None
        )
        if hazard is None:
            target_clean = values.target_id.strip()
            is_stat = values.device_type == "HAZARD_STATIONARY" or target_clean.startswith(("S-", "L", "G", "M"))
            hazard = {
                "id": target_clean,
                "name": assignment or f"Hazard {target_clean}",
                "type": "LASER" if target_clean.startswith(("L", "S-LSR")) else "GRINDING" if target_clean.startswith(("G", "S-GRD")) else "CONTAINER_CRANE" if target_clean.startswith(("C", "M-CNT")) else "FORKLIFT",
                "category": "STATIONARY" if is_stat else "MOBILE",
                "status": "ACTIVE",
                "area": "Gudang Utama",
                "online": False,
                "last_update": now,
                "alias": target_clean,
                "beacon_name": f"RK_{'S' if is_stat else 'M'}_{target_clean.replace('-', '_')}"[:15],
            }
            simulation_engine.state["hazards"].append(hazard)
            assignment = hazard["name"]
        else:
            assignment = assignment or hazard["name"]
            if values.assignment:
                hazard["name"] = assignment
                for worker in simulation_engine.state["workers"]:
                    if worker.get("closest_hazard") in (hazard["id"], hazard.get("alias")):
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
    
    if device["type"] in ("HAZARD_NODE", "HAZARD_MOBILE", "HAZARD_STATIONARY") or device_id.startswith(("HAZARD-", "DEV-BCN-")):
        hazard_id = device_id.replace("HAZARD-", "").replace("DEV-BCN-", "")
        simulation_engine.state["hazards"] = [h for h in simulation_engine.state["hazards"] if h["id"] != hazard_id and h.get("alias") != hazard_id]
        
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
    sync_today_history()
    history = simulation_engine.state["history"]
    return history[-1:] if period == "today" else history[-7:] if period == "7d" else history


@router.get("/analytics/risk-trend", tags=["Analytics"])
async def risk_trend(period: str = "7d") -> dict[str, Any]:
    return {"items": filtered_history(period), "simulation_data": True}


@router.get("/analytics/near-miss-trend", tags=["Analytics"])
async def near_miss_trend(period: str = "7d") -> dict[str, Any]:
    history = filtered_history(period)
    types_found = {event.get("hazard_type", "UNKNOWN") for event in simulation_engine.state.get("near_misses", [])}
    for h in simulation_engine.state.get("hazards", []):
        if h.get("type"):
            types_found.add(h["type"])
    by_type = [
        {"type": hazard_type, "count": sum(event["hazard_type"] == hazard_type for event in simulation_engine.state["near_misses"])}
        for hazard_type in sorted(types_found)
    ]
    return {"items": history, "by_type": by_type, "simulation_data": True}


@router.get("/analytics/exposure", tags=["Analytics"])
async def exposure(period: str = "7d") -> dict[str, Any]:
    hazards_list = simulation_engine.state.get("hazards", [])
    workers_list = simulation_engine.state.get("workers", [])
    by_hazard = []
    for hazard in hazards_list:
        hz_id = hazard["id"]
        hz_alias = hazard.get("alias")
        nearby = [w for w in workers_list if w.get("closest_hazard") in (hz_id, hz_alias)]
        nm_events = [e for e in simulation_engine.state.get("near_misses", []) if e.get("hazard_id") in (hz_id, hz_alias)]
        total_mins = sum(w.get("exposure_seconds", 0) for w in nearby) // 60 + len(nm_events) * 6
        by_hazard.append({
            "name": hazard["name"],
            "minutes": max(5, total_mins),
            "frequency": len(nm_events) + len(nearby),
        })
    return {"items": filtered_history(period), "by_hazard": by_hazard, "simulation_data": True}


@router.get("/analytics/device-uptime", tags=["Analytics"])
async def device_uptime(period: str = "7d") -> dict[str, Any]:
    devices = simulation_engine.state.get("devices", [])
    uptime = round((sum(d.get("online", False) for d in devices) / max(1, len(devices))) * 100, 1)
    return {"items": filtered_history(period), "average_uptime": uptime, "simulation_data": True}


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
    if {"mobile_moderate_rssi", "mobile_high_rssi", "mobile_critical_rssi"} & set(updates):
        merged = {**SYSTEM_SETTINGS, **updates}
        if not merged["mobile_moderate_rssi"] < merged["mobile_high_rssi"] < merged["mobile_critical_rssi"]:
            raise HTTPException(status_code=422, detail="Threshold Mobile RSSI harus berurutan: moderate < high < critical")
    if {"stationary_moderate_rssi", "stationary_high_rssi", "stationary_critical_rssi"} & set(updates):
        merged = {**SYSTEM_SETTINGS, **updates}
        if not merged["stationary_moderate_rssi"] < merged["stationary_high_rssi"] < merged["stationary_critical_rssi"]:
            raise HTTPException(status_code=422, detail="Threshold Stationary RSSI harus berurutan: moderate < high < critical")
    SYSTEM_SETTINGS.update(updates)
    await db_service.persist_settings(updates)
    return {"values": SYSTEM_SETTINGS, "message": "Pengaturan tersimpan"}


@router.get("/profile", tags=["Profile"])
async def get_profile() -> dict[str, Any]:
    return {
        "name": CURRENT_USER_PROFILE["name"],
        "role": CURRENT_USER_PROFILE["role"],
        "initials": calculate_initials(CURRENT_USER_PROFILE["name"]),
    }


@router.put("/profile", tags=["Profile"])
async def update_profile(values: ProfileInput) -> dict[str, Any]:
    CURRENT_USER_PROFILE["name"] = values.name
    CURRENT_USER_PROFILE["role"] = values.role
    await db_service.persist_profile(values.name, values.role)
    response_data = {
        "name": CURRENT_USER_PROFILE["name"],
        "role": CURRENT_USER_PROFILE["role"],
        "initials": calculate_initials(CURRENT_USER_PROFILE["name"]),
    }
    await websocket_manager.broadcast("profile.updated", response_data)
    return response_data


@router.post("/simulation/reset", tags=["Simulation"])
async def simulation_reset() -> dict[str, Any]:
    await simulation_engine.reset()
    return simulation_engine.get_status()


@router.post("/warnings/test", tags=["Warnings"])
async def test_warning(values: WarningInput) -> dict[str, Any]:
    find(simulation_engine.state["workers"], values.worker_id)
    warning = warning_service.create(
        values.worker_id,
        values.level.upper(),
        values.reason or "Uji Peringatan Helm oleh Supervisor",
        buzzer=values.buzzer,
        vibration=values.vibration,
        duration_ms=values.duration_ms,
        is_test=True,
    )
    simulation_engine.state["warnings"].insert(0, warning)
    simulation_engine.state.setdefault("activities", []).insert(0, {
        "id": f"act-wrn-{warning['warning_id']}",
        "type": "WARNING",
        "message": f"Uji sinyal buzzer dikirim ke helm pekerja {values.worker_id}",
        "timestamp": warning["timestamp"],
    })
    
    from app.main import mqtt_service
    mqtt_service.publish(warning["mqtt_topic"], warning)
    
    await websocket_manager.broadcast("warning.created", warning)
    await db_service.persist_warning(warning)
    return warning


@router.post("/warnings/send", tags=["Warnings"])
async def send_warning(values: WarningInput) -> dict[str, Any]:
    find(simulation_engine.state["workers"], values.worker_id)
    if values.buzzer and not values.confirmed:
        raise HTTPException(status_code=400, detail="Konfirmasi wajib sebelum mengaktifkan buzzer")
    is_test = "uji" in (values.reason or "").casefold() or "test" in (values.reason or "").casefold()
    warning = warning_service.create(
        values.worker_id,
        values.level.upper(),
        values.reason,
        buzzer=values.buzzer,
        vibration=values.vibration,
        duration_ms=values.duration_ms,
        is_test=is_test,
    )
    simulation_engine.state["warnings"].insert(0, warning)
    simulation_engine.state.setdefault("activities", []).insert(0, {
        "id": f"act-wrn-{warning['warning_id']}",
        "type": "WARNING",
        "message": f"Sinyal buzzer/getar dikirim ke pekerja {values.worker_id} · {values.reason}",
        "timestamp": warning["timestamp"],
    })
    
    from app.main import mqtt_service
    mqtt_service.publish(warning["mqtt_topic"], warning)
    
    await websocket_manager.broadcast("warning.created", warning)
    await db_service.persist_warning(warning)
    return warning


@router.get("/warnings", tags=["Warnings"])
async def warnings() -> dict[str, Any]:
    return {"items": simulation_engine.state["warnings"], "total": len(simulation_engine.state["warnings"]), "simulation_data": True}


class VoiceAcknowledgeInput(BaseModel):
    supervisor_note: str = Field(default="Diverifikasi dan ditangani oleh supervisor", max_length=500)
    action_taken: str = Field(default="ACKNOWLEDGED", max_length=100)


class VoiceSimulateInput(BaseModel):
    worker_id: str = Field(default="W01")
    transcription: str = Field(min_length=1, max_length=500)


@router.get("/voice/transmissions", tags=["Voice Comms"])
async def get_voice_transmissions() -> dict[str, Any]:
    from app.services.voice_service import voice_service

    items = simulation_engine.state.get("voice_transmissions", [])
    return {
        "items": items,
        "total": len(items),
        "latest": items[0] if items else None,
        "audio_available": voice_service.has_audio(),
    }


@router.api_route("/voice/latest-audio", methods=["GET", "HEAD"], tags=["Voice Comms"])
async def get_latest_voice_audio():
    from app.services.voice_service import generate_synthetic_dispatch_tone, voice_service

    audio_bytes = voice_service.latest_audio
    if not audio_bytes:
        items = simulation_engine.state.get("voice_transmissions", [])
        if items and items[0].get("audio_data_uri"):
            try:
                uri = items[0]["audio_data_uri"]
                b64_part = uri.split(",", 1)[1] if "," in uri else uri
                audio_bytes = base64.b64decode(b64_part)
                voice_service.latest_audio = audio_bytes
            except Exception:
                pass
    if not audio_bytes:
        audio_bytes = generate_synthetic_dispatch_tone()
        voice_service.latest_audio = audio_bytes

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Content-Disposition": 'inline; filename="latest_voice.wav"',
            "Accept-Ranges": "bytes",
            "Content-Length": str(len(audio_bytes)),
        },
    )


@router.api_route("/voice/audio/{transmission_id}", methods=["GET", "HEAD"], tags=["Voice Comms"])
async def get_transmission_audio(transmission_id: str):
    from app.services.voice_service import generate_synthetic_dispatch_tone, voice_service

    audio_bytes = voice_service.get_audio(transmission_id)
    if not audio_bytes:
        items = simulation_engine.state.get("voice_transmissions", [])
        trans = next((t for t in items if t["id"] == transmission_id), None)
        if trans and trans.get("audio_data_uri"):
            try:
                uri = trans["audio_data_uri"]
                b64_part = uri.split(",", 1)[1] if "," in uri else uri
                audio_bytes = base64.b64decode(b64_part)
                voice_service.audio_cache[transmission_id] = audio_bytes
            except Exception:
                pass
        if not audio_bytes:
            audio_bytes = generate_synthetic_dispatch_tone()
            voice_service.audio_cache[transmission_id] = audio_bytes

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Content-Disposition": f'inline; filename="{transmission_id}.wav"',
            "Accept-Ranges": "bytes",
            "Content-Length": str(len(audio_bytes)),
        },
    )


@router.post("/voice/transmissions/{transmission_id}/acknowledge", tags=["Voice Comms"])
async def acknowledge_voice_transmission(transmission_id: str, payload: VoiceAcknowledgeInput) -> dict[str, Any]:
    items = simulation_engine.state.get("voice_transmissions", [])
    trans = next((t for t in items if t["id"] == transmission_id), None)
    if not trans:
        raise HTTPException(status_code=404, detail="Transmisi suara tidak ditemukan")

    trans["acknowledged"] = True
    trans["acknowledged_by"] = f"{CURRENT_USER_PROFILE['name']} ({CURRENT_USER_PROFILE['role']})"
    trans["supervisor_note"] = payload.supervisor_note
    trans["action_taken"] = payload.action_taken
    trans["acknowledged_at"] = datetime.now(UTC).isoformat()

    await websocket_manager.broadcast("voice.transmission_acknowledged", trans)
    return trans


@router.post("/voice/transmissions/{transmission_id}/broadcast-alarm", tags=["Voice Comms"])
async def broadcast_alarm_for_voice(transmission_id: str) -> dict[str, Any]:
    items = simulation_engine.state.get("voice_transmissions", [])
    trans = next((t for t in items if t["id"] == transmission_id), None)
    if not trans:
        raise HTTPException(status_code=404, detail="Transmisi suara tidak ditemukan")

    worker_id = trans["worker_id"]
    reason = f"Alarm Balasan Suara K3: {trans['intent_label']} - {trans['transcription'][:60]}"
    warning = warning_service.create(
        worker_id,
        "CRITICAL",
        reason,
        buzzer=True,
        vibration=True,
        duration_ms=4000,
    )
    simulation_engine.state["warnings"].insert(0, warning)

    from app.main import mqtt_service
    mqtt_service.publish(warning["mqtt_topic"], warning)
    await websocket_manager.broadcast("warning.created", warning)

    trans["alarm_dispatched"] = True
    trans["action_taken"] = "ALARM_DISPATCHED_TO_HELMET"
    trans["supervisor_note"] = "Peringatan darurat dikirim balik ke helm pekerja via MQTT buzzer/vibration."
    await websocket_manager.broadcast("voice.transmission_updated", trans)

    return {"message": "Alarm darurat berhasil dikirim balik ke helm pekerja", "warning": warning, "transmission": trans}


@router.post("/voice/simulate", tags=["Voice Comms"])
async def simulate_voice_transmission(payload: VoiceSimulateInput) -> dict[str, Any]:
    from app.services.voice_service import generate_synthetic_dispatch_tone, parse_safety_intent, voice_service

    worker = next(
        (w for w in simulation_engine.state.get("workers", []) if w["id"] == payload.worker_id),
        None,
    )
    hazards = simulation_engine.state.get("hazards", [])
    nlu_result = parse_safety_intent(payload.transcription, worker, hazards)
    now_str = datetime.now(UTC).isoformat()
    time_code = datetime.now(UTC).strftime("%H%M%S")
    transmission_id = f"VT-SIM-{time_code}"

    synth_wav = generate_synthetic_dispatch_tone()
    b64_audio = base64.b64encode(synth_wav).decode("ascii")
    audio_data_uri = f"data:audio/wav;base64,{b64_audio}"
    voice_service.audio_cache[transmission_id] = synth_wav
    voice_service.latest_audio = synth_wav
    try:
        os.makedirs("/tmp/reksa_audio", exist_ok=True)
        with open(f"/tmp/reksa_audio/{transmission_id}.wav", "wb") as f:
            f.write(synth_wav)
        with open("/tmp/reksa_audio/latest_voice.wav", "wb") as f:
            f.write(synth_wav)
    except Exception:
        pass

    matched_hz = nlu_result["matched_hazard"]
    transmission = {
        "id": transmission_id,
        "timestamp": now_str,
        "worker_id": payload.worker_id,
        "worker_name": worker["name"] if worker else f"Pekerja {payload.worker_id}",
        "worker_role": worker.get("role", "Operator") if worker else "Operator",
        "area": nlu_result["detected_area"],
        "transcription": payload.transcription,
        "intent": nlu_result["intent"],
        "intent_label": nlu_result["intent_label"],
        "urgency": nlu_result["urgency"],
        "nature": nlu_result["nature"],
        "confidence": nlu_result["confidence"],
        "target_hazard_id": matched_hz.get("id") if matched_hz else None,
        "target_hazard_name": matched_hz.get("name") if matched_hz else None,
        "target_hazard_type": matched_hz.get("type") if matched_hz else None,
        "recommended_action": nlu_result["recommended_action"],
        "acknowledged": False,
        "acknowledged_by": None,
        "supervisor_note": "",
        "audio_available": True,
        "audio_url": f"/api/v1/voice/audio/{transmission_id}",
        "audio_data_uri": audio_data_uri,
    }

    if "voice_transmissions" not in simulation_engine.state:
        simulation_engine.state["voice_transmissions"] = []
    simulation_engine.state["voice_transmissions"].insert(0, transmission)

    if nlu_result["urgency"] in ("CRITICAL", "HIGH"):
        nm_event = {
            "id": f"NM-V{time_code}",
            "timestamp": now_str,
            "worker_id": payload.worker_id,
            "worker_name": worker["name"] if worker else payload.worker_id,
            "hazard_id": matched_hz.get("id") if matched_hz else (worker.get("closest_hazard") or "F01"),
            "hazard_name": matched_hz.get("name") if matched_hz else (worker.get("hazard_name") or "Laporan Bahaya Suara"),
            "hazard_type": matched_hz.get("type") if matched_hz else "VOICE_HAZARD",
            "proximity": "CRITICAL" if nlu_result["urgency"] == "CRITICAL" else "HIGH",
            "rssi": worker.get("rssi", -52) if worker else -52,
            "duration": 5.0,
            "hazard_status": "ACTIVE",
            "risk_score": 96 if nlu_result["urgency"] == "CRITICAL" else 76,
            "risk_level": nlu_result["urgency"],
            "warning_status": "DELIVERED",
            "acknowledged": False,
            "note": f"Laporan Suara ({nlu_result['intent_label']}): \"{payload.transcription}\"",
        }
        if "near_misses" in simulation_engine.state:
            simulation_engine.state["near_misses"].insert(0, nm_event)
        await websocket_manager.broadcast("near_miss.created", nm_event)

        if worker:
            if nlu_result["urgency"] == "CRITICAL":
                worker["risk_level"] = "CRITICAL"
                worker["risk_score"] = max(worker.get("risk_score", 0), 96)
            elif nlu_result["urgency"] == "HIGH" and worker.get("risk_level") not in ("CRITICAL", "HIGH"):
                worker["risk_level"] = "HIGH"
                worker["risk_score"] = max(worker.get("risk_score", 0), 76)
            worker["dominant_factor"] = f"Laporan Suara ({nlu_result['intent_label']})"
            worker["recommended_action"] = nlu_result["recommended_action"]
            await websocket_manager.broadcast("worker.updated", worker)

    if "activities" in simulation_engine.state:
        simulation_engine.state["activities"].insert(0, {
            "id": f"act-v{time_code}",
            "type": "VOICE_DISPATCH",
            "message": f"Transmisi Suara [{nlu_result['urgency']}] {transmission['worker_name']}: \"{payload.transcription}\"",
            "timestamp": now_str,
        })

    await websocket_manager.broadcast("voice.transmission", transmission)
    await websocket_manager.broadcast("voice.command", {
        "worker_id": payload.worker_id,
        "transcription": payload.transcription,
        "action": nlu_result["intent"],
        "urgency": nlu_result["urgency"],
        "message": nlu_result["intent_label"],
    })

    return transmission
