from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.entities import (
    NearMissEvent,
    ProximityReading,
    SensorReading,
    SupervisorAcknowledgement,
    SystemSetting,
    WarningEvent,
    Worker,
)
from app.services.db_service import DatabaseService


@pytest.fixture
def service():
    return DatabaseService()


def test_persist_near_miss_and_acknowledgement(service: DatabaseService):
    test_code = "NM-TEST-PERSIST-999"
    event_data = {
        "id": test_code,
        "timestamp": datetime.now(UTC).isoformat(),
        "worker_id": "W01",
        "worker_name": "Andi Pratama",
        "hazard_id": "F01",
        "hazard_name": "Forklift Alpha",
        "hazard_type": "FORKLIFT",
        "rssi": -38.0,
        "duration": 7.5,
        "hazard_status": "MOVING",
        "risk_score": 95,
        "warning_status": "DELIVERED",
        "acknowledged": False,
        "note": "",
    }

    service.persist_near_miss_sync(event_data)

    with SessionLocal() as db:
        nm = db.scalar(select(NearMissEvent).where(NearMissEvent.event_code == test_code))
        assert nm is not None
        assert nm.risk_score == 95
        assert nm.acknowledged is False

    service.persist_acknowledgement_sync(test_code, "Supervisor Test", "Verifikasi lapangan aman")

    with SessionLocal() as db:
        nm = db.scalar(select(NearMissEvent).where(NearMissEvent.event_code == test_code))
        assert nm.acknowledged is True
        assert nm.supervisor_note == "Verifikasi lapangan aman"

        ack = db.scalar(select(SupervisorAcknowledgement).where(SupervisorAcknowledgement.near_miss_id == nm.id))
        assert ack is not None
        assert ack.supervisor_name == "Supervisor Test"

        db.delete(nm)
        db.commit()


def test_persist_sensor_reading_telemetry(service: DatabaseService):
    payload = {
        "temperature": 31.2,
        "humidity": 68.5,
        "impact_detected": True,
        "impact_g": 3.2,
        "air_quality": {"mq135_raw": 1100, "gas_alert": True},
        "closest_hazard": {
            "hazard_id": "F01",
            "hazard_name": "Forklift Alpha",
            "hazard_type": "FORKLIFT",
            "rssi": -42.0,
            "proximity_level": "CRITICAL",
        },
    }

    service._last_sensor_log.clear()
    service.persist_sensor_reading_sync("W01", payload, movement_status="BERGERAK")

    with SessionLocal() as db:
        worker = db.scalar(select(Worker).where(Worker.worker_code == "W01"))
        assert worker is not None

        sr = db.scalar(
            select(SensorReading)
            .where(SensorReading.worker_id == worker.id)
            .order_by(SensorReading.recorded_at.desc())
        )
        assert sr is not None
        assert sr.impact_detected is True
        assert sr.raw_payload["impact_g"] == 3.2

        pr = db.scalar(
            select(ProximityReading)
            .where(ProximityReading.worker_id == worker.id)
            .order_by(ProximityReading.recorded_at.desc())
        )
        assert pr is not None
        assert pr.raw_rssi == -42.0

        db.delete(pr)
        db.delete(sr)
        db.commit()


def test_persist_warning_event(service: DatabaseService):
    warn_code = "WARN-TEST-PERSIST-888"
    warn_data = {
        "warning_id": warn_code,
        "worker_id": "W01",
        "warning_level": "HIGH",
        "actions": {"vibration": True, "buzzer": True},
        "duration_ms": 4000,
        "reason": "Test buzzer getar integrasi",
        "status": "PUBLISHED",
    }

    service.persist_warning_sync(warn_data)

    with SessionLocal() as db:
        we = db.scalar(select(WarningEvent).where(WarningEvent.warning_code == warn_code))
        assert we is not None
        assert we.buzzer is True
        assert we.vibration is True
        assert we.duration_ms == 4000

        db.delete(we)
        db.commit()


def test_persist_and_load_settings(service: DatabaseService):
    test_settings = {"test_custom_rssi": -55}
    service.persist_settings_sync(test_settings)

    loaded = service.load_settings_from_db()
    assert loaded.get("test_custom_rssi") == -55

    with SessionLocal() as db:
        st = db.scalar(select(SystemSetting).where(SystemSetting.key == "test_custom_rssi"))
        if st:
            db.delete(st)
            db.commit()
