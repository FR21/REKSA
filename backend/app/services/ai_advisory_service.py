import logging
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger("reksa.ai_advisory")

PROXIMITY_MAP = {
    "CRITICAL": "CRITICAL",
    "DANGER": "CRITICAL",
    "KRITIS": "CRITICAL",
    "HIGH": "HIGH",
    "TINGGI": "HIGH",
    "WARNING": "HIGH",
    "MODERATE": "MODERATE",
    "MEDIUM": "MODERATE",
    "SEDANG": "MODERATE",
    "CAUTION": "MODERATE",
    "SAFE": "SAFE",
    "AMAN": "SAFE",
}


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
        acceleration_g = {
            axis: float(acceleration.get(axis, 0.0)) / 9.80665 for axis in ("x", "y", "z")
        }
        raw_rssi = float(payload.get("closest_hazard", {}).get("rssi") or -100.0)
        if raw_rssi > 0:
            raw_rssi = -raw_rssi
        clamped_rssi = max(-120.0, min(0.0, raw_rssi))

        gyro_raw = payload.get("gyroscope") or {}
        gyroscope = {axis: float(gyro_raw.get(axis, 0.0)) for axis in ("x", "y", "z")}

        orient_raw = payload.get("orientation") or {}
        orientation = {axis: float(orient_raw.get(axis, 0.0)) for axis in ("pitch", "roll", "yaw")}

        prox_clean = PROXIMITY_MAP.get(proximity.upper(), "SAFE")

        return {
            "timestamp": payload.get("timestamp") or datetime.now(UTC).isoformat(),
            "rssi": clamped_rssi,
            "packet_received": True,
            "acceleration": acceleration_g,
            "gyroscope": gyroscope,
            "orientation": orientation,
            "proximity_level": prox_clean,
            "hazard_active": bool(hazard_active),
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

        worker_id = str(payload.get("worker_id", "UNKNOWN"))[:40]
        hazard_id = str(closest.get("hazard_id", "UNKNOWN"))[:40]
        raw_prox = str(closest.get("proximity_level", "SAFE")).upper()
        proximity = PROXIMITY_MAP.get(raw_prox, "SAFE")
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

        # Ensure timestamps in samples are strictly increasing and formatted
        sanitized_samples = []
        last_dt = None
        for s in samples:
            dt = self._parse_timestamp(s["timestamp"])
            if last_dt is not None and dt <= last_dt:
                dt = last_dt + timedelta(milliseconds=10)
            last_dt = dt
            s_clean = dict(s)
            s_clean["timestamp"] = dt.isoformat()
            sanitized_samples.append(s_clean)

        msg_id = str(payload.get("message_id") or "msg")[:30]
        window_id = f"{key}:{msg_id}"[:100]

        request = {
            "window_id": window_id,
            "worker_id": worker_id,
            "helmet_id": str(payload.get("device_id") or worker_id)[:80],
            "hazard_id": hazard_id,
            "hazard_type": str(closest.get("hazard_type", "UNKNOWN"))[:60],
            "samples": sanitized_samples,
        }
        try:
            response = await self._client.post(f"{self.base_url}/v1/forecast", json=request)
            response.raise_for_status()
            result = response.json()
            result["status"] = "READY"
            result["sample_count"] = len(sanitized_samples)
            return result
        except httpx.HTTPError as error:
            resp_body = getattr(getattr(error, "response", None), "text", "")
            logger.warning("AI forecast error: %s (%s)", error, resp_body)
            return {
                "status": "UNAVAILABLE",
                "error": type(error).__name__,
                "detail": resp_body[:200] if resp_body else str(error),
                "sample_count": len(sanitized_samples),
                "advisory_only": True,
                "generated_at": datetime.now(UTC).isoformat(),
            }
        except ValueError as error:
            logger.warning("AI payload validation error: %s", error)
            return {
                "status": "UNAVAILABLE",
                "error": "ValueError",
                "sample_count": len(sanitized_samples),
                "advisory_only": True,
                "generated_at": datetime.now(UTC).isoformat(),
            }
