from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from pytest import MonkeyPatch

from app.services import mqtt_service as mqtt_service_module
from app.services.mqtt_service import MQTTService


def helmet_payload() -> dict[str, object]:
    return {
        "message_id": "delivery-1",
        "device_id": "HELMET-W01",
        "worker_id": "W01",
        "timestamp": datetime.now(UTC).isoformat(),
        "acceleration": {"x": 0, "y": 0, "z": 9.80665},
        "gyroscope": {"x": 0, "y": 0, "z": 0},
        "orientation": {"pitch": 0, "roll": 0, "yaw": 0},
        "impact_detected": False,
        "fall_detected": False,
        "closest_hazard": None,
        "firmware_version": "0.3.0",
    }


def test_duplicate_message_is_processed_once_and_acknowledged_twice() -> None:
    handled: list[dict[str, object]] = []
    acknowledgements: list[tuple[str, dict[str, object]]] = []
    service = MQTTService("localhost", 1883, handler=lambda _topic, payload: handled.append(payload))

    def publish(topic: str, payload: str, **_kwargs: object) -> SimpleNamespace:
        acknowledgements.append((topic, json.loads(payload)))
        return SimpleNamespace(rc=0)

    service.client.publish = publish  # type: ignore[method-assign]
    message = SimpleNamespace(
        topic="REKSA/helmet/W01/sensor",
        payload=json.dumps(helmet_payload()).encode(),
    )
    service._on_message(service.client, None, message)
    service._on_message(service.client, None, message)

    assert len(handled) == 1
    assert len(acknowledgements) == 2
    assert acknowledgements[0][0] == "REKSA/helmet/W01/telemetry/ack"
    assert acknowledgements[1][1]["duplicate"] is True


def test_empty_ca_cert_uses_operating_system_trust_store(monkeypatch: MonkeyPatch) -> None:
    tls_options: dict[str, object] = {}

    def capture_tls_options(_client: object, **options: object) -> None:
        tls_options.update(options)

    monkeypatch.setattr(
        mqtt_service_module.mqtt.Client,
        "tls_set",
        capture_tls_options,
    )
    MQTTService("broker.example", 8883, use_tls=True, ca_cert="")

    assert tls_options["ca_certs"] is None
