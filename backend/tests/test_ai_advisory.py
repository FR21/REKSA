from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.services.ai_advisory_service import AIAdvisoryService


def helmet_payload(timestamp: datetime, message_id: str, rssi: int) -> dict[str, object]:
    return {
        "message_id": message_id,
        "device_id": "HELMET-W01",
        "worker_id": "W01",
        "timestamp": timestamp.isoformat(),
        "acceleration": {"x": 0.0, "y": 0.0, "z": 9.80665},
        "gyroscope": {"x": 1.0, "y": 2.0, "z": 3.0},
        "orientation": {"pitch": 0.0, "roll": 0.0, "yaw": 0.0},
        "closest_hazard": {
            "hazard_id": "F01",
            "hazard_type": "FORKLIFT",
            "operating_status": "MOVING",
            "rssi": rssi,
            "proximity_level": "HIGH",
        },
    }


@pytest.mark.asyncio
async def test_temporal_window_calls_ai_and_preserves_metadata() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "window_id": "window",
                "worker_id": "W01",
                "hazard_id": "F01",
                "escalation_probability": 0.72,
                "risk_level": "HIGH",
                "dominant_factors": ["rapid_rssi_increase"],
                "recommendation": "Tingkatkan pemantauan.",
                "inference_source": "RULE_BASED_BASELINE",
                "model_version": "forecast-rule-v1",
                "probability_is_calibrated": False,
                "score_semantics": "RULE_SCORE",
                "advisory_only": True,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )

    service = AIAdvisoryService(
        "http://ai", min_samples=2, transport=httpx.MockTransport(handler)
    )
    now = datetime.now(UTC)
    first = await service.analyze_helmet_payload(helmet_payload(now, "m1", -72))
    second = await service.analyze_helmet_payload(
        helmet_payload(now + timedelta(seconds=1), "m2", -60)
    )
    await service.close()

    assert first["status"] == "COLLECTING_WINDOW"
    assert second["status"] == "READY"
    assert second["inference_source"] == "RULE_BASED_BASELINE"
    assert second["probability_is_calibrated"] is False
    assert captured["samples"][0]["acceleration"]["z"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_ai_failure_is_explicit_and_never_invents_probability() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    service = AIAdvisoryService(
        "http://ai", min_samples=2, transport=httpx.MockTransport(handler)
    )
    now = datetime.now(UTC)
    await service.analyze_helmet_payload(helmet_payload(now, "m1", -72))
    result = await service.analyze_helmet_payload(
        helmet_payload(now + timedelta(seconds=1), "m2", -60)
    )
    await service.close()

    assert result["status"] == "UNAVAILABLE"
    assert "escalation_probability" not in result
    assert result["advisory_only"] is True
