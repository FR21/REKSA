from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


class AIAdvisoryService:
    """Build temporal windows and request advisory inference.

    Safety alarms never depend on this service. When inference is unavailable,
    callers receive an explicit status instead of an invented probability.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 2.0,
        window_seconds: float = 10.0,
        min_samples: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.window_seconds = window_seconds
        self.min_samples = min_samples
        self._samples: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
        self._client = httpx.AsyncClient(timeout=timeout_seconds, transport=transport)

    async def close(self) -> None:
        await self._client.aclose()

    def _sample(self, payload: dict[str, Any], proximity: str, hazard_active: bool) -> dict[str, Any]:
        acceleration = payload.get("acceleration") or {}
        # Firmware telemetry is expressed in m/s². The AI contract uses g.
        acceleration_g = {
            axis: float(acceleration.get(axis, 0.0)) / 9.80665 for axis in ("x", "y", "z")
        }
        return {
            "timestamp": payload["timestamp"],
            "rssi": float(payload["closest_hazard"]["rssi"]),
            "packet_received": True,
            "acceleration": acceleration_g,
            "gyroscope": payload.get("gyroscope") or {"x": 0, "y": 0, "z": 0},
            "orientation": payload.get("orientation") or {"pitch": 0, "roll": 0, "yaw": 0},
            "proximity_level": proximity,
            "hazard_active": hazard_active,
        }

    @staticmethod
    def _parse_timestamp(value: str | datetime) -> datetime:
        timestamp = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        return timestamp.astimezone(UTC)

    def _append(self, key: str, sample: dict[str, Any]) -> list[dict[str, Any]]:
        samples = self._samples[key]
        samples.append(sample)
        newest = self._parse_timestamp(sample["timestamp"])
        cutoff = newest - timedelta(seconds=self.window_seconds)
        while samples and self._parse_timestamp(samples[0]["timestamp"]) < cutoff:
            samples.popleft()
        return list(samples)

    async def analyze_helmet_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        closest = payload.get("closest_hazard")
        if not closest:
            return {
                "status": "AWAITING_HAZARD",
                "advisory_only": True,
                "generated_at": datetime.now(UTC).isoformat(),
            }

        worker_id = str(payload["worker_id"])
        hazard_id = str(closest["hazard_id"])
        proximity = str(closest.get("proximity_level", "SAFE")).upper()
        operating_status = str(closest.get("operating_status", "INACTIVE")).upper()
        hazard_active = operating_status in {"ACTIVE", "MOVING", "RUNNING"}
        key = f"{worker_id}:{hazard_id}"
        samples = self._append(key, self._sample(payload, proximity, hazard_active))

        if len(samples) < self.min_samples:
            return {
                "status": "COLLECTING_WINDOW",
                "sample_count": len(samples),
                "required_samples": self.min_samples,
                "advisory_only": True,
                "generated_at": datetime.now(UTC).isoformat(),
            }

        request = {
            "window_id": f"{key}:{payload['message_id']}",
            "worker_id": worker_id,
            "helmet_id": str(payload["device_id"]),
            "hazard_id": hazard_id,
            "hazard_type": str(closest.get("hazard_type", "UNKNOWN")),
            "samples": samples,
        }
        try:
            response = await self._client.post(f"{self.base_url}/v1/forecast", json=request)
            response.raise_for_status()
            result = response.json()
            result["status"] = "READY"
            result["sample_count"] = len(samples)
            return result
        except (httpx.HTTPError, ValueError) as error:
            return {
                "status": "UNAVAILABLE",
                "error": type(error).__name__,
                "sample_count": len(samples),
                "advisory_only": True,
                "generated_at": datetime.now(UTC).isoformat(),
            }
