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
