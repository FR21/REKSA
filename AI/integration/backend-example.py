"""Contoh adapter; pindahkan pola ini ke service backend REKSA saat integrasi."""

from typing import Any

import httpx


async def request_event_priority(event_payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url="http://reksa-ai:8100", timeout=2.0) as client:
        response = await client.post("/v1/prioritize", json=event_payload)
        response.raise_for_status()
        result = response.json()
        if not result.get("advisory_only"):
            raise ValueError("AI contract violation: advisory_only must be true")
        return result


async def request_live_forecast(window_payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url="http://reksa-ai:8100", timeout=1.0) as client:
        response = await client.post("/v1/forecast", json=window_payload)
        response.raise_for_status()
        return response.json()
