from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Zone(StrEnum):
    SAFE = "SAFE"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AdvisoryLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SupervisorPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Vector3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float


class Orientation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pitch: float
    roll: float
    yaw: float


class SensorSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    rssi: float | None = Field(default=None, ge=-120, le=0)
    packet_received: bool = True
    acceleration: Vector3
    gyroscope: Vector3
    orientation: Orientation
    proximity_level: Zone = Zone.SAFE
    hazard_active: bool = False

    @model_validator(mode="after")
    def require_rssi_for_received_packet(self) -> SensorSample:
        if self.packet_received and self.rssi is None:
            raise ValueError("rssi is required when packet_received=true")
        return self


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_id: str = Field(min_length=1, max_length=100)
    worker_id: str = Field(min_length=1, max_length=40)
    helmet_id: str = Field(min_length=1, max_length=80)
    hazard_id: str = Field(min_length=1, max_length=40)
    hazard_type: str = Field(default="UNKNOWN", min_length=1, max_length=60)
    repeated_exposure_count: int = Field(default=0, ge=0)
    samples: list[SensorSample] = Field(min_length=2, max_length=600)

    @field_validator("samples")
    @classmethod
    def timestamps_must_be_unique_and_orderable(
        cls, samples: list[SensorSample]
    ) -> list[SensorSample]:
        timestamps = [sample.timestamp for sample in samples]
        if len(set(timestamps)) != len(timestamps):
            raise ValueError("sample timestamps must be unique")
        return sorted(samples, key=lambda sample: sample.timestamp)


class TemporalFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_duration_seconds: float = Field(ge=0)
    sample_count: int = Field(ge=2)
    rssi_mean: float = Field(ge=-120, le=0)
    rssi_peak: float = Field(ge=-120, le=0)
    rssi_min: float = Field(ge=-120, le=0)
    rssi_std: float = Field(ge=0)
    rssi_slope: float
    warning_duration_seconds: float = Field(ge=0)
    danger_duration_seconds: float = Field(ge=0)
    state_transition_count: int = Field(ge=0)
    packet_loss_ratio: float = Field(ge=0, le=1)
    acceleration_mean_g: float = Field(ge=0)
    acceleration_max_g: float = Field(ge=0)
    acceleration_energy: float = Field(ge=0)
    gyroscope_mean_dps: float = Field(ge=0)
    gyroscope_max_dps: float = Field(ge=0)
    gyroscope_energy: float = Field(ge=0)
    orientation_change_deg: float = Field(ge=0)
    sudden_motion: bool
    hazard_active: bool
    repeated_exposure_count: int = Field(ge=0)
    hazard_type: str


class PriorityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=100)
    worker_id: str = Field(min_length=1, max_length=40)
    helmet_id: str = Field(min_length=1, max_length=80)
    hazard_id: str = Field(min_length=1, max_length=40)
    hazard_type: str = Field(default="UNKNOWN", min_length=1, max_length=60)
    occurred_at: datetime
    event_duration_seconds: float = Field(ge=0)
    rssi_mean: float = Field(ge=-120, le=0)
    rssi_peak: float = Field(ge=-120, le=0)
    rssi_min: float = Field(ge=-120, le=0)
    rssi_std: float = Field(ge=0)
    rssi_slope: float
    warning_duration_seconds: float = Field(ge=0)
    danger_duration_seconds: float = Field(ge=0)
    state_transition_count: int = Field(ge=0)
    packet_loss_count: int = Field(ge=0)
    acceleration_max_g: float = Field(ge=0)
    gyroscope_max_dps: float = Field(ge=0)
    orientation_change_deg: float = Field(ge=0)
    sudden_motion: bool = False
    candidate_impact: bool = False
    candidate_fall: bool = False
    post_event_stillness_seconds: float = Field(default=0, ge=0)
    temperature_c: float | None = Field(default=None, ge=-20, le=100)
    humidity_percent: float | None = Field(default=None, ge=0, le=100)
    mq135_deviation: float | None = None
    hazard_active: bool = False
    alarm_level: Zone = Zone.SAFE
    local_warning_success: bool = True
    repeated_exposure_count: int = Field(default=0, ge=0)
    similar_event_count: int = Field(default=0, ge=0)
    connectivity_status: str = Field(default="ONLINE", max_length=30)


class ForecastResponse(BaseModel):
    engine: str = "NEAR_MISS_RISK_FORECASTER"
    window_id: str
    worker_id: str
    hazard_id: str
    escalation_probability: float = Field(ge=0, le=1)
    risk_level: AdvisoryLevel
    dominant_factors: list[str]
    explanation_method: str = "THRESHOLD_REASON_CODES"
    recommendation: str
    inference_source: str
    model_version: str
    probability_is_calibrated: bool
    score_semantics: str
    advisory_only: bool = True
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PriorityResponse(BaseModel):
    engine: str = "AI_PRIORITY_ENGINE"
    event_id: str
    worker_id: str
    priority: SupervisorPriority
    priority_score: int = Field(ge=0, le=100)
    reason_codes: list[str]
    explanation: str
    explanation_method: str = "THRESHOLD_REASON_CODES"
    recommended_action: str
    inference_source: str
    model_version: str
    advisory_only: bool = True
    requires_supervisor_verification: bool = True
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CombinedAnalysisRequest(BaseModel):
    current_window: ForecastRequest | None = None
    completed_event: PriorityEvent | None = None

    @model_validator(mode="after")
    def require_at_least_one_payload(self) -> CombinedAnalysisRequest:
        if self.current_window is None and self.completed_event is None:
            raise ValueError("current_window or completed_event is required")
        return self


class CombinedAnalysisResponse(BaseModel):
    forecast: ForecastResponse | None = None
    priority_assessment: PriorityResponse | None = None
