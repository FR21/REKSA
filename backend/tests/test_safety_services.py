from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.mqtt import HelmetSensorPayload
from app.schemas.risk import RiskFeatures
from app.services.device_service import is_device_offline
from app.services.exposure_service import ExposureService, ExposureState
from app.services.near_miss_service import NearMissService
from app.services.proximity_service import ProximityService, ProximityThresholds
from app.services.risk_engine_service import RiskEngine, classify_risk
from app.services.warning_service import WarningService


def test_proximity_classification_boundaries() -> None:
    service = ProximityService()
    assert service.classify(-71) == "SAFE"
    assert service.classify(-70) == "MODERATE"
    assert service.classify(-60) == "HIGH"
    assert service.classify(-45) == "CRITICAL"


def test_rssi_smoothing_and_consecutive_transition() -> None:
    service = ProximityService(ProximityThresholds(window_size=3, consecutive_readings=2))
    smoothed, level = service.add_reading("W01:F01", -50)
    assert smoothed == -50
    assert level == "SAFE"
    _, level = service.add_reading("W01:F01", -50)
    assert level == "HIGH"


def test_invalid_rssi_is_filtered() -> None:
    service = ProximityService()
    smoothed, level = service.add_reading("pair", 25)
    assert smoothed == -120
    assert level == "SAFE"


def test_exposure_duration() -> None:
    service = ExposureService()
    start = datetime.now(UTC)
    service.update("pair", "CRITICAL", -42, start)
    state = service.update("pair", "CRITICAL", -40, start + timedelta(seconds=7))
    assert state is not None
    assert state.duration_seconds == 7


def test_near_miss_threshold_and_cooldown() -> None:
    now = datetime.now(UTC)
    state = ExposureState(now - timedelta(seconds=6), now, [-42, -40], "CRITICAL")
    service = NearMissService(critical_duration=5, cooldown_seconds=30)
    assert service.should_create("pair", state, "MOVING", now)
    assert not service.should_create("pair", state, "MOVING", now + timedelta(seconds=2))
    assert service.should_create("pair", state, "MOVING", now + timedelta(seconds=31))


def test_near_miss_requires_active_hazard() -> None:
    now = datetime.now(UTC)
    state = ExposureState(now - timedelta(seconds=8), now, [-40], "CRITICAL")
    assert not NearMissService().should_create("pair", state, "INACTIVE", now)


@pytest.mark.parametrize("score, level", [(0, "SAFE"), (24, "SAFE"), (25, "MODERATE"), (50, "HIGH"), (75, "CRITICAL"), (100, "CRITICAL")])
def test_risk_level_classification(score: int, level: str) -> None:
    assert classify_risk(score) == level


def test_rule_based_scoring_is_deterministic_and_normalized() -> None:
    engine = RiskEngine()
    features = RiskFeatures(hazard_exposure=1, near_miss_count=10, activity_risk=1, heat_exposure=1, work_duration=24, impact_status=True)
    first = engine.score(features)
    second = engine.score(features)
    assert first == second
    assert first.risk_score == 100
    assert first.calculation_source == "RULE_BASED_SCORING"


def test_invalid_mqtt_payload_is_rejected() -> None:
    with pytest.raises(ValidationError):
        HelmetSensorPayload.model_validate({"message_id": "bad", "temperature": 130})


def test_helmet_payload_accepts_environment_readings() -> None:
    payload = HelmetSensorPayload.model_validate({
        "message_id": "msg-test",
        "device_id": "HELMET-W01",
        "worker_id": "W01",
        "timestamp": datetime.now(UTC).isoformat(),
        "acceleration": {"x": 0, "y": 0, "z": 9.8},
        "gyroscope": {"x": 0, "y": 0, "z": 0},
        "orientation": {"pitch": 0, "roll": 0, "yaw": 0},
        "impact_detected": False,
        "fall_detected": False,
        "closest_hazard": None,
        "temperature": 31.5,
        "humidity": 72.0,
        "firmware_version": "0.1.0",
    })

    assert payload.temperature == 31.5
    assert payload.humidity == 72.0


def test_device_offline_detection() -> None:
    now = datetime.now(UTC)
    assert is_device_offline(now - timedelta(seconds=31), now, 30)
    assert not is_device_offline(now - timedelta(seconds=29), now, 30)


def test_warning_creation_is_bounded() -> None:
    warning = WarningService().create("W01", "CRITICAL", "Test", buzzer=True, duration_ms=50_000)
    assert warning["actions"] == {"vibration": True, "buzzer": True}
    assert warning["duration_ms"] == 10_000
    assert warning["mqtt_topic"] == "REKSA/helmet/W01/warning"
