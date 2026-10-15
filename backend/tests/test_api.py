import base64
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.main import app


@pytest.fixture
def transport() -> httpx.ASGITransport:
    return httpx.ASGITransport(app=app)


@pytest.mark.asyncio
async def test_health(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_dashboard_seeded(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    assert response.json()["active_workers"] == 5
    assert response.json()["simulation_data"] is True


@pytest.mark.asyncio
async def test_worker_detail_never_invents_ai_probability(
    transport: httpx.ASGITransport,
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/workers/W01")
    advisory = response.json()["ai_advisory"]
    assert advisory["status"] == "AWAITING_LIVE_TELEMETRY"
    assert "escalation_probability" not in advisory


@pytest.mark.asyncio
async def test_near_miss_acknowledgement(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        event = (await client.get("/api/v1/near-misses")).json()["items"][0]
        response = await client.patch(
            f"/api/v1/near-misses/{event['id']}/acknowledge",
            json={"supervisor_name": "Tester", "note": "Sudah aman"},
        )
    assert response.status_code == 200
    assert response.json()["acknowledged"] is True


@pytest.mark.asyncio
async def test_settings_require_confirmation(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch("/api/v1/settings", json={"critical_rssi": -44})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_buzzer_requires_confirmation(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/warnings/send", json={"worker_id": "W01", "buzzer": True}
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_pubsub_push_replays_original_mqtt_envelope(transport: httpx.ASGITransport) -> None:
    payload = {
        "message_id": "pubsub-test-1",
        "device_id": "HELMET-W01",
        "worker_id": "W01",
        "timestamp": datetime.now(UTC).isoformat(),
        "acceleration": {"x": 0, "y": 0, "z": 9.80665},
        "gyroscope": {"x": 0, "y": 0, "z": 0},
        "orientation": {"pitch": 0, "roll": 0, "yaw": 0},
        "impact_detected": False,
        "fall_detected": False,
        "firmware_version": "0.3.0",
        "closest_hazard": None,
    }
    envelope = {"topic": "REKSA/helmet/W01/sensor", "payload": payload}
    encoded = base64.b64encode(json.dumps(envelope).encode()).decode()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ingest/pubsub",
            json={"message": {"data": encoded, "messageId": "gcp-message-1"}},
        )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_pubsub_push_rejects_invalid_envelope(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ingest/pubsub",
            json={"message": {"data": "not-base64", "messageId": "bad"}},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_hazard_and_pair_standard_device(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        hz_res = await client.post(
            "/api/v1/hazards",
            json={
                "id": "M-FLK-09",
                "name": "Forklift Titan",
                "type": "FORKLIFT",
                "category": "MOBILE",
                "area": "Gudang Utama",
            },
        )
        assert hz_res.status_code == 200
        hz_data = hz_res.json()["hazard"]
        assert hz_data["id"] == "M-FLK-09"
        assert hz_data["beacon_name"] == "RK_M_FLK09"

        pair_res = await client.post(
            "/api/v1/devices/pair",
            json={
                "device_id": "DEV-BCN-M-FLK09",
                "device_type": "HAZARD_MOBILE",
                "target_id": "M-FLK-09",
                "assignment": "Forklift Titan",
            },
        )
        assert pair_res.status_code == 200
        dev = pair_res.json()["device"]
        assert dev["id"] == "DEV-BCN-M-FLK09"
        assert dev["topic"] == "REKSA/hazard/M-FLK-09/beacon"


@pytest.mark.asyncio
async def test_get_and_update_profile(transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        get_res = await client.get("/api/v1/profile")
        assert get_res.status_code == 200
        data = get_res.json()
        assert "name" in data
        assert "role" in data
        assert "initials" in data

        put_res = await client.put(
            "/api/v1/profile",
            json={"name": "Ahmad Dani", "role": "HSE Manager"},
        )
        assert put_res.status_code == 200
        updated = put_res.json()
        assert updated["name"] == "Ahmad Dani"
        assert updated["role"] == "HSE Manager"
        assert updated["initials"] == "AD"

        # Verify get returns updated profile
        verify_res = await client.get("/api/v1/profile")
        assert verify_res.status_code == 200
        assert verify_res.json()["name"] == "Ahmad Dani"

