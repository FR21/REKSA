from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    Device,
    EnvironmentNode,
    Hazard,
    HazardDevice,
    HelmetDevice,
    NearMissEvent,
    RiskAssessment,
    RiskLevel,
    SystemSetting,
    Worker,
)
from app.simulation.state import build_state


def seed_database(db: Session) -> None:
    if db.scalar(select(Worker.id).limit(1)) is not None:
        return
    state = build_state(42)
    workers_by_code: dict[str, Worker] = {}
    hazards_by_code: dict[str, Hazard] = {}

    for item in state["workers"]:
        worker = Worker(worker_code=item["id"], name=item["name"], area=item["area"], role=item["role"], active=True)
        db.add(worker)
        db.flush()
        workers_by_code[item["id"]] = worker
        device = Device(device_code=f"HELMET-{item['id']}", device_type="SMART_HELMET", online=item["online"], last_seen=datetime.now(UTC), firmware_version="0.1.0", signal_quality=82 if item["online"] else 0, mqtt_topic=f"REKSA/helmet/{item['id']}/sensor", metadata_json={"data_source": "SIMULATION"})
        db.add(device)
        db.flush()
        db.add(HelmetDevice(device_id=device.id, worker_id=worker.id))

    for item in state["hazards"]:
        hazard = Hazard(hazard_code=item["id"], name=item["name"], hazard_type=item["type"], operating_status=item["status"], area=item["area"], position_x=item["x"], position_y=item["y"])
        db.add(hazard)
        db.flush()
        hazards_by_code[item["id"]] = hazard
        device = Device(device_code=f"HAZARD-{item['id']}", device_type="HAZARD_NODE", online=True, last_seen=datetime.now(UTC), firmware_version="0.1.0", signal_quality=76, mqtt_topic=f"REKSA/hazard/{item['id']}/beacon", metadata_json={"data_source": "SIMULATION"})
        db.add(device)
        db.flush()
        db.add(HazardDevice(device_id=device.id, hazard_id=hazard.id))

    for index, area in enumerate(["Gudang Utama", "Produksi A"], start=1):
        code = f"E{index:02}"
        device = Device(device_code=f"ENV-{code}", device_type="ENVIRONMENT_NODE", online=True, last_seen=datetime.now(UTC), firmware_version="0.1.0", signal_quality=79, mqtt_topic=f"REKSA/environment/{code}/data", metadata_json={"data_source": "SIMULATION"})
        db.add(device)
        db.flush()
        db.add(EnvironmentNode(environment_code=code, device_id=device.id, area=area))

    for worker_code, worker in workers_by_code.items():
        worker_index = int(worker_code[-1])
        for day, point in enumerate(state["history"]):
            score = max(5, min(100, point["average_risk"] + (worker_index - 3) * 3))
            level = RiskLevel.CRITICAL if score >= 75 else RiskLevel.HIGH if score >= 50 else RiskLevel.MODERATE if score >= 25 else RiskLevel.SAFE
            db.add(RiskAssessment(worker_id=worker.id, assessed_at=datetime.now(UTC) - timedelta(days=13 - day), risk_score=score, risk_level=level, calculation_source="RULE_BASED_SCORING", explanation_details={"data_source": "SIMULATION", "hazard_exposure": score / 100}))

    for event in state["near_misses"]:
        db.add(NearMissEvent(event_code=event["id"], worker_id=workers_by_code[event["worker_id"]].id, hazard_id=hazards_by_code[event["hazard_id"]].id, occurred_at=datetime.fromisoformat(event["timestamp"]), critical_duration=event["duration"], maximum_rssi=event["rssi"], average_rssi=event["rssi"] - 2, hazard_status=event["hazard_status"], risk_score=event["risk_score"], warning_status=event["warning_status"], acknowledged=event["acknowledged"], supervisor_note=event["note"] or None))

    for key, value in {"moderate_rssi": -70, "high_rssi": -60, "critical_rssi": -45, "critical_exposure_duration": 5, "device_offline_timeout": 30, "warning_cooldown": 30}.items():
        db.add(SystemSetting(key=key, value_json={"value": value}, description=f"Configurable {key.replace('_', ' ')}", safety_critical=True))
    db.commit()
