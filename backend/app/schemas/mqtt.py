from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Vector3(BaseModel):
    x: float
    y: float
    z: float


class Orientation(BaseModel):
    pitch: float
    roll: float
    yaw: float


class ClosestHazard(BaseModel):
    hazard_id: str
    hazard_type: str
    operating_status: str
    rssi: float = Field(ge=-120, le=0)
    proximity_level: str


class AirQuality(BaseModel):
    mq135_raw: int = Field(ge=0, le=4095)
    air_quality_level: str
    gas_alert: bool


class HelmetSensorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str
    device_id: str
    worker_id: str
    timestamp: datetime
    acceleration: Vector3
    gyroscope: Vector3
    orientation: Orientation
    impact_detected: bool
    fall_detected: bool
    impact_g: float | None = Field(default=None, ge=0, le=16)
    closest_hazard: ClosestHazard | None = None
    air_quality: AirQuality | None = None
    temperature: float | None = Field(default=None, ge=-20, le=100)
    humidity: float | None = Field(default=None, ge=0, le=100)
    firmware_version: str


class Position(BaseModel):
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


class HazardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str
    device_id: str
    hazard_id: str
    hazard_type: str
    timestamp: datetime
    operating_status: str
    movement_detected: bool
    speed_level: str
    position: Position


class EnvironmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str
    device_id: str
    environment_id: str
    timestamp: datetime
    temperature: float = Field(ge=-20, le=100)
    humidity: float = Field(ge=0, le=100)
    area: str

    @field_validator("area")
    @classmethod
    def normalize_area(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("area cannot be empty")
        return value
