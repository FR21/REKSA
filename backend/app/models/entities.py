import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.base import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class RiskLevel(enum.StrEnum):
    SAFE = "SAFE"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TimestampMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Worker(TimestampMixin, Base):
    __tablename__ = "workers"
    worker_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    area: Mapped[str] = mapped_column(String(80), index=True)
    role: Mapped[str] = mapped_column(String(80), default="Operator")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    helmet: Mapped["HelmetDevice | None"] = relationship(back_populates="worker")


class Device(TimestampMixin, Base):
    __tablename__ = "devices"
    device_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    device_type: Mapped[str] = mapped_column(String(30), index=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    firmware_version: Mapped[str | None] = mapped_column(String(30))
    signal_quality: Mapped[int | None] = mapped_column(Integer)
    mqtt_topic: Mapped[str] = mapped_column(String(180))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)


class HelmetDevice(TimestampMixin, Base):
    __tablename__ = "helmet_devices"
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), unique=True)
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), unique=True)
    worker: Mapped[Worker] = relationship(back_populates="helmet")


class Hazard(TimestampMixin, Base):
    __tablename__ = "hazards"
    hazard_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    hazard_type: Mapped[str] = mapped_column(String(40), index=True)
    operating_status: Mapped[str] = mapped_column(String(30), index=True)
    area: Mapped[str] = mapped_column(String(80), index=True)
    position_x: Mapped[float] = mapped_column(Float)
    position_y: Mapped[float] = mapped_column(Float)


class HazardDevice(TimestampMixin, Base):
    __tablename__ = "hazard_devices"
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), unique=True)
    hazard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hazards.id", ondelete="CASCADE"), unique=True)


class EnvironmentNode(TimestampMixin, Base):
    __tablename__ = "environment_nodes"
    environment_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), unique=True)
    area: Mapped[str] = mapped_column(String(80), index=True)


class SensorReading(TimestampMixin, Base):
    __tablename__ = "sensor_readings"
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    impact_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    movement_status: Mapped[str] = mapped_column(String(30))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT)
    __table_args__ = (Index("ix_sensor_worker_time", "worker_id", "recorded_at"),)


class EnvironmentReading(TimestampMixin, Base):
    __tablename__ = "environment_readings"
    environment_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environment_nodes.id", ondelete="CASCADE"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)


class ProximityReading(TimestampMixin, Base):
    __tablename__ = "proximity_readings"
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    hazard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hazards.id", ondelete="CASCADE"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    raw_rssi: Mapped[float] = mapped_column(Float)
    smoothed_rssi: Mapped[float] = mapped_column(Float)
    proximity_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), index=True)
    __table_args__ = (Index("ix_proximity_pair_time", "worker_id", "hazard_id", "recorded_at"),)


class ExposureSession(TimestampMixin, Base):
    __tablename__ = "exposure_sessions"
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    hazard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hazards.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    max_rssi: Mapped[float] = mapped_column(Float)
    average_rssi: Mapped[float] = mapped_column(Float)
    level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), index=True)


class NearMissEvent(TimestampMixin, Base):
    __tablename__ = "near_miss_events"
    event_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    hazard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hazards.id", ondelete="CASCADE"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    critical_duration: Mapped[float] = mapped_column(Float)
    maximum_rssi: Mapped[float] = mapped_column(Float)
    average_rssi: Mapped[float] = mapped_column(Float)
    hazard_status: Mapped[str] = mapped_column(String(30))
    risk_score: Mapped[int] = mapped_column(Integer)
    warning_status: Mapped[str] = mapped_column(String(30))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    supervisor_note: Mapped[str | None] = mapped_column(Text)


class RiskAssessment(TimestampMixin, Base):
    __tablename__ = "risk_assessments"
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), index=True)
    calculation_source: Mapped[str] = mapped_column(String(40))
    explanation_details: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT)


class WarningEvent(TimestampMixin, Base):
    __tablename__ = "warning_events"
    warning_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    warning_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), index=True)
    vibration: Mapped[bool] = mapped_column(Boolean)
    buzzer: Mapped[bool] = mapped_column(Boolean)
    duration_ms: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), index=True)


class SupervisorAcknowledgement(TimestampMixin, Base):
    __tablename__ = "supervisor_acknowledgements"
    near_miss_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("near_miss_events.id", ondelete="CASCADE"), index=True)
    supervisor_name: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SystemSetting(TimestampMixin, Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    description: Mapped[str] = mapped_column(String(250))
    safety_critical: Mapped[bool] = mapped_column(Boolean, default=False)
