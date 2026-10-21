from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.entities import (
    Hazard,
    NearMissEvent,
    ProximityReading,
    RiskLevel,
    SensorReading,
    SupervisorAcknowledgement,
    SystemSetting,
    WarningEvent,
    Worker,
)

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self) -> None:
        self._worker_cache: dict[str, uuid.UUID] = {}
        self._hazard_cache: dict[str, uuid.UUID] = {}
        self._last_sensor_log: dict[str, float] = {}
        self._sensor_throttle_seconds: float = 15.0

    def _get_worker(self, db: Session, worker_code: str, name: str | None = None) -> Worker:
        cached_id = self._worker_cache.get(worker_code)
        if cached_id:
            worker = db.get(Worker, cached_id)
            if worker:
                return worker

        worker = db.scalar(select(Worker).where(Worker.worker_code == worker_code))
        if not worker:
            worker = Worker(
                worker_code=worker_code,
                name=name or f"Worker {worker_code}",
                area="Area Kerja",
                role="Operator",
                active=True,
            )
            db.add(worker)
            db.flush()
        self._worker_cache[worker_code] = worker.id
        return worker

    def _get_hazard(
        self,
        db: Session,
        hazard_code: str,
        name: str | None = None,
        hazard_type: str | None = None,
    ) -> Hazard:
        cached_id = self._hazard_cache.get(hazard_code)
        if cached_id:
            hazard = db.get(Hazard, cached_id)
            if hazard:
                return hazard

        hazard = db.scalar(
            select(Hazard).where(
                (Hazard.hazard_code == hazard_code) | (Hazard.name == (name or hazard_code))
            )
        )
        if not hazard:
            clean_type = hazard_type or ("FORKLIFT" if "FLK" in hazard_code or "F0" in hazard_code else "HAZARD")
            hazard = Hazard(
                hazard_code=hazard_code,
                name=name or f"Hazard {hazard_code}",
                hazard_type=clean_type,
                operating_status="ACTIVE",
                area="Area Kerja",
                position_x=0.0,
                position_y=0.0,
            )
            db.add(hazard)
            db.flush()
        self._hazard_cache[hazard_code] = hazard.id
        return hazard

    # Near miss persistence
    def persist_near_miss_sync(self, event: dict[str, Any]) -> None:
        event_code = event.get("id")
        if not event_code:
            return

        with SessionLocal() as db:
            try:
                worker_id_str = event.get("worker_id", "W01")
                hazard_id_str = event.get("hazard_id", "F01")
                worker = self._get_worker(db, worker_id_str, event.get("worker_name"))
                hazard = self._get_hazard(db, hazard_id_str, event.get("hazard_name"), event.get("hazard_type"))

                existing = db.scalar(select(NearMissEvent).where(NearMissEvent.event_code == event_code))
                if existing:
                    existing.acknowledged = event.get("acknowledged", existing.acknowledged)
                    existing.supervisor_note = event.get("note") or existing.supervisor_note
                else:
                    ts_str = event.get("timestamp")
                    occurred_at = datetime.fromisoformat(ts_str) if ts_str else datetime.now(UTC)
                    nm = NearMissEvent(
                        event_code=event_code,
                        worker_id=worker.id,
                        hazard_id=hazard.id,
                        occurred_at=occurred_at,
                        critical_duration=float(event.get("duration", 5.0)),
                        maximum_rssi=float(event.get("rssi", -50.0)),
                        average_rssi=float(event.get("rssi", -50.0)) - 2.0,
                        hazard_status=str(event.get("hazard_status", "ACTIVE")),
                        risk_score=int(event.get("risk_score", 90)),
                        warning_status=str(event.get("warning_status", "DELIVERED")),
                        acknowledged=bool(event.get("acknowledged", False)),
                        supervisor_note=event.get("note") or None,
                    )
                    db.add(nm)
                db.commit()
                logger.info("Persisted near miss event %s to database", event_code)
            except Exception as exc:
                db.rollback()
                logger.error("Failed to persist near miss %s: %s", event_code, exc)

    async def persist_near_miss(self, event: dict[str, Any]) -> None:
        await asyncio.to_thread(self.persist_near_miss_sync, event)

    # Acknowledgment & note persistence
    def persist_acknowledgement_sync(self, event_code: str, supervisor_name: str, note: str) -> None:
        with SessionLocal() as db:
            try:
                nm = db.scalar(select(NearMissEvent).where(NearMissEvent.event_code == event_code))
                if not nm:
                    logger.warning("NearMiss %s not found in DB for acknowledgement", event_code)
                    return
                nm.acknowledged = True
                if note:
                    nm.supervisor_note = note
                ack = SupervisorAcknowledgement(
                    near_miss_id=nm.id,
                    supervisor_name=supervisor_name,
                    note=note or None,
                    acknowledged_at=datetime.now(UTC),
                )
                db.add(ack)
                db.commit()
                logger.info("Persisted acknowledgement for near miss %s", event_code)
            except Exception as exc:
                db.rollback()
                logger.error("Failed to persist acknowledgement %s: %s", event_code, exc)

    async def persist_acknowledgement(self, event_code: str, supervisor_name: str, note: str) -> None:
        await asyncio.to_thread(self.persist_acknowledgement_sync, event_code, supervisor_name, note)

    def persist_near_miss_note_sync(self, event_code: str, note: str) -> None:
        with SessionLocal() as db:
            try:
                nm = db.scalar(select(NearMissEvent).where(NearMissEvent.event_code == event_code))
                if nm:
                    nm.supervisor_note = note
                    db.commit()
                    logger.info("Updated note for near miss %s", event_code)
            except Exception as exc:
                db.rollback()
                logger.error("Failed to persist note for near miss %s: %s", event_code, exc)

    async def persist_near_miss_note(self, event_code: str, note: str) -> None:
        await asyncio.to_thread(self.persist_near_miss_note_sync, event_code, note)

    # Sensor reading telemetry (AI/ML feature store)
    def persist_sensor_reading_sync(
        self,
        worker_code: str,
        payload: dict[str, Any],
        movement_status: str = "BERGERAK",
    ) -> None:
        now_ts = time.time()
        is_impact = bool(payload.get("impact_detected") or payload.get("fall_detected"))
        air_quality = payload.get("air_quality") or {}
        is_gas_alert = bool(air_quality.get("gas_alert") or payload.get("gas_alert"))
        closest_hazard = payload.get("closest_hazard") or {}
        is_critical_proximity = closest_hazard.get("proximity_level") in ("CRITICAL", "HIGH")

        # Smart throttle: immediate flush on high-value safety anomaly, else sample periodically
        is_high_value_sample = is_impact or is_gas_alert or is_critical_proximity
        last_logged = self._last_sensor_log.get(worker_code, 0.0)
        if not is_high_value_sample and (now_ts - last_logged < self._sensor_throttle_seconds):
            return

        self._last_sensor_log[worker_code] = now_ts

        with SessionLocal() as db:
            try:
                worker = self._get_worker(db, worker_code)
                recorded_at = datetime.now(UTC)

                reading = SensorReading(
                    worker_id=worker.id,
                    recorded_at=recorded_at,
                    impact_detected=is_impact,
                    movement_status=movement_status,
                    raw_payload=payload,
                )
                db.add(reading)

                if closest_hazard and closest_hazard.get("hazard_id"):
                    hz_code = closest_hazard.get("hazard_id")
                    hz_name = closest_hazard.get("hazard_name") or f"Hazard {hz_code}"
                    hazard = self._get_hazard(db, hz_code, hz_name, closest_hazard.get("hazard_type"))
                    raw_rssi = float(closest_hazard.get("rssi", -100.0))
                    prox_str = closest_hazard.get("proximity_level", "SAFE").upper()
                    prox_enum = (
                        RiskLevel.CRITICAL if prox_str == "CRITICAL"
                        else RiskLevel.HIGH if prox_str == "HIGH"
                        else RiskLevel.MODERATE if prox_str == "MODERATE"
                        else RiskLevel.SAFE
                    )

                    prox = ProximityReading(
                        worker_id=worker.id,
                        hazard_id=hazard.id,
                        recorded_at=recorded_at,
                        raw_rssi=raw_rssi,
                        smoothed_rssi=raw_rssi,
                        proximity_level=prox_enum,
                    )
                    db.add(prox)

                db.commit()
                logger.debug("Persisted sensor telemetry for worker %s to DB", worker_code)
            except Exception as exc:
                db.rollback()
                logger.error("Failed to persist sensor telemetry for %s: %s", worker_code, exc)

    async def persist_sensor_reading(
        self,
        worker_code: str,
        payload: dict[str, Any],
        movement_status: str = "BERGERAK",
    ) -> None:
        await asyncio.to_thread(self.persist_sensor_reading_sync, worker_code, payload, movement_status)

    # Warning event persistence
    def persist_warning_sync(self, warning_dict: dict[str, Any]) -> None:
        warning_code = warning_dict.get("warning_id")
        if not warning_code:
            return

        with SessionLocal() as db:
            try:
                worker = self._get_worker(db, warning_dict.get("worker_id", "W01"))
                level_str = warning_dict.get("warning_level", "HIGH").upper()
                level_enum = (
                    RiskLevel.CRITICAL if level_str == "CRITICAL"
                    else RiskLevel.HIGH if level_str == "HIGH"
                    else RiskLevel.MODERATE if level_str == "MODERATE"
                    else RiskLevel.SAFE
                )
                actions = warning_dict.get("actions", {})

                we = WarningEvent(
                    warning_code=warning_code,
                    worker_id=worker.id,
                    warning_level=level_enum,
                    vibration=bool(actions.get("vibration", True)),
                    buzzer=bool(actions.get("buzzer", False)),
                    duration_ms=int(warning_dict.get("duration_ms", 3000)),
                    reason=str(warning_dict.get("reason", "Safety alert")),
                    status=str(warning_dict.get("status", "PUBLISHED")),
                )
                db.add(we)
                db.commit()
                logger.info("Persisted warning event %s to database", warning_code)
            except Exception as exc:
                db.rollback()
                logger.error("Failed to persist warning %s: %s", warning_code, exc)

    async def persist_warning(self, warning_dict: dict[str, Any]) -> None:
        await asyncio.to_thread(self.persist_warning_sync, warning_dict)

    # System settings persistence
    def persist_settings_sync(self, settings_dict: dict[str, Any]) -> None:
        with SessionLocal() as db:
            try:
                for key, value in settings_dict.items():
                    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
                    if setting:
                        setting.value_json = {"value": value}
                    else:
                        db.add(
                            SystemSetting(
                                key=key,
                                value_json={"value": value},
                                description=f"Safety threshold {key.replace('_', ' ')}",
                                safety_critical=True,
                            )
                        )
                db.commit()
                logger.info("Persisted %d system settings to database", len(settings_dict))
            except Exception as exc:
                db.rollback()
                logger.error("Failed to persist settings: %s", exc)

    async def persist_settings(self, settings_dict: dict[str, Any]) -> None:
        await asyncio.to_thread(self.persist_settings_sync, settings_dict)

    # Warm cache from DB
    def load_near_misses_from_db(self) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            try:
                query = (
                    db.query(NearMissEvent, Worker, Hazard)
                    .join(Worker, NearMissEvent.worker_id == Worker.id)
                    .join(Hazard, NearMissEvent.hazard_id == Hazard.id)
                    .order_by(NearMissEvent.occurred_at.desc())
                    .limit(100)
                )
                results: list[dict[str, Any]] = []
                for nm, w, h in query:
                    results.append({
                        "id": nm.event_code,
                        "timestamp": nm.occurred_at.isoformat(),
                        "worker_id": w.worker_code,
                        "worker_name": w.name,
                        "hazard_id": h.hazard_code,
                        "hazard_name": h.name,
                        "hazard_type": h.hazard_type,
                        "proximity": "CRITICAL" if nm.risk_score >= 75 else "HIGH",
                        "rssi": nm.maximum_rssi,
                        "duration": nm.critical_duration,
                        "hazard_status": nm.hazard_status,
                        "risk_score": nm.risk_score,
                        "risk_level": "CRITICAL" if nm.risk_score >= 75 else "HIGH",
                        "warning_status": nm.warning_status,
                        "acknowledged": nm.acknowledged,
                        "note": nm.supervisor_note or "",
                    })
                return results
            except Exception as exc:
                logger.error("Failed to load near misses from DB: %s", exc)
                return []

    def load_settings_from_db(self) -> dict[str, Any]:
        with SessionLocal() as db:
            try:
                settings_rows = db.scalars(select(SystemSetting)).all()
                out: dict[str, Any] = {}
                for row in settings_rows:
                    val = row.value_json.get("value") if isinstance(row.value_json, dict) else row.value_json
                    out[row.key] = val
                return out
            except Exception as exc:
                logger.error("Failed to load settings from DB: %s", exc)
                return {}

    def get_profile_sync(self) -> dict[str, str]:
        with SessionLocal() as db:
            try:
                setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "user_profile"))
                if setting and isinstance(setting.value_json, dict):
                    name = setting.value_json.get("name", "Raka Wijaya")
                    role = setting.value_json.get("role", "Supervisor K3")
                    return {"name": name, "role": role}
                initial_profile = {"name": "Raka Wijaya", "role": "Supervisor K3"}
                db.add(
                    SystemSetting(
                        key="user_profile",
                        value_json=initial_profile,
                        description="Active supervisor profile",
                        safety_critical=False,
                    )
                )
                db.commit()
                return initial_profile
            except Exception as exc:
                logger.error("Failed to load user profile: %s", exc)
                return {"name": "Raka Wijaya", "role": "Supervisor K3"}

    async def get_profile(self) -> dict[str, str]:
        return await asyncio.to_thread(self.get_profile_sync)

    def persist_profile_sync(self, name: str, role: str) -> dict[str, str]:
        with SessionLocal() as db:
            try:
                setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "user_profile"))
                if setting:
                    setting.value_json = {"name": name, "role": role}
                else:
                    db.add(
                        SystemSetting(
                            key="user_profile",
                            value_json={"name": name, "role": role},
                            description="Active supervisor profile",
                            safety_critical=False,
                        )
                    )
                db.commit()
                logger.info("Persisted user profile for %s (%s) to database", name, role)
                return {"name": name, "role": role}
            except Exception as exc:
                db.rollback()
                logger.error("Failed to persist user profile: %s", exc)
                return {"name": name, "role": role}

    async def persist_profile(self, name: str, role: str) -> dict[str, str]:
        return await asyncio.to_thread(self.persist_profile_sync, name, role)


db_service = DatabaseService()
