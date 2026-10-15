import pytest

from app.core.config import settings
from app.services.voice_service import get_wit_ai_token, parse_safety_intent


def test_parse_safety_intent_emergency_id():
    worker = {"name": "Budi", "area": "Gudang Utama"}
    hazards = [{"id": "F01", "name": "Forklift Alpha", "type": "forklift"}]
    result = parse_safety_intent("Tolong evakuasi gudang utama, ada kebakaran!", worker, hazards)
    assert result["intent"] == "EMERGENCY_EVACUATE"
    assert result["urgency"] == "CRITICAL"
    assert result["detected_area"] == "Gudang Utama"
    assert "Assembly Point" in result["recommended_action"]


def test_parse_safety_intent_emergency_en():
    worker = {"name": "John", "area": "Main Warehouse"}
    hazards = [{"id": "F01", "name": "Forklift Alpha", "type": "forklift"}]
    result = parse_safety_intent("Mayday help me, worker injured in main warehouse!", worker, hazards)
    assert result["intent"] == "ASSISTANCE_SOS"
    assert result["urgency"] == "CRITICAL"
    assert result["detected_area"] == "Gudang Utama"
    assert "tim medis" in result["recommended_action"].lower()


def test_parse_safety_intent_machine_halt_with_hazard():
    worker = {"name": "Rudi", "area": "Zona Bongkar"}
    hazards = [{"id": "F01", "name": "Forklift Alpha", "type": "forklift"}]
    result = parse_safety_intent("Stop machine, brake failure on forklift!", worker, hazards)
    assert result["intent"] == "MACHINE_HALT"
    assert result["urgency"] == "HIGH"
    assert result["matched_hazard"]["id"] == "F01"
    assert "Forklift Alpha" in result["recommended_action"]


def test_parse_safety_intent_hazard_report():
    worker = {"name": "Siti", "area": "Produksi A"}
    hazards = [{"id": "G01", "name": "Grinding Machine 1", "type": "grinding"}]
    result = parse_safety_intent("Ada tumpahan oli dan kabel lepas di zona bongkar", worker, hazards)
    assert result["intent"] == "HAZARD_REPORT"
    assert result["urgency"] == "HIGH"
    assert result["detected_area"] == "Zona Bongkar"


def test_parse_safety_intent_status_safe():
    worker = {"name": "Eko", "area": "Produksi B"}
    hazards = []
    result = parse_safety_intent("Semua aman terkendali di line b, roger that", worker, hazards)
    assert result["intent"] == "SAFETY_STATUS"
    assert result["urgency"] == "INFO"
    assert result["detected_area"] == "Produksi B"


def test_parse_safety_intent_fallback_closest_hazard():
    worker = {"name": "Anton", "area": "Area Kerja", "closest_hazard": "F01"}
    hazards = [{"id": "F01", "name": "Forklift Alpha", "type": "forklift"}]
    result = parse_safety_intent("Awas bahaya!", worker, hazards)
    assert result["intent"] == "HAZARD_REPORT"
    assert result["matched_hazard"]["id"] == "F01"


def test_get_wit_ai_token(monkeypatch):
    monkeypatch.setenv("WIT_AI_TOKEN", "TEST_TOKEN_123")
    settings.wit_ai_token = "TEST_TOKEN_123"
    token = get_wit_ai_token()
    assert token == "Bearer TEST_TOKEN_123"


@pytest.fixture
def transport():
    import httpx

    from app.main import app
    return httpx.ASGITransport(app=app)


@pytest.mark.asyncio
async def test_voice_transmissions_api_lifecycle(transport):
    import httpx

    from app.services.voice_service import voice_service

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/voice/simulate",
            json={"worker_id": "W01", "transcription": "Tolong evakuasi gudang utama, kebakaran!"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "EMERGENCY_EVACUATE"
        trans_id = data["id"]

        get_res = await client.get("/api/v1/voice/transmissions")
        assert get_res.status_code == 200
        items = get_res.json()["items"]
        assert any(item["id"] == trans_id for item in items)

        # Set in-memory audio without writing to disk
        voice_service.latest_audio = b"RIFFmockwavdata"
        voice_service.audio_cache[trans_id] = b"RIFFmockwavdata"

        audio_res = await client.get(f"/api/v1/voice/audio/{trans_id}")
        assert audio_res.status_code == 200
        assert audio_res.headers["content-type"] == "audio/wav"
        assert audio_res.content == b"RIFFmockwavdata"

        latest_res = await client.get("/api/v1/voice/latest-audio")
        assert latest_res.status_code == 200
        assert latest_res.headers["content-type"] == "audio/wav"

        ack_res = await client.post(
            f"/api/v1/voice/transmissions/{trans_id}/acknowledge",
            json={"supervisor_note": "Tim SAR meluncur", "action_taken": "DISPATCHED"},
        )
        assert ack_res.status_code == 200
        assert ack_res.json()["acknowledged"] is True
        assert ack_res.json()["supervisor_note"] == "Tim SAR meluncur"

