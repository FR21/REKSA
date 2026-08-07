import uuid
from datetime import UTC, datetime
from typing import Any


class WarningService:
    def create(
        self,
        worker_id: str,
        level: str,
        reason: str,
        *,
        buzzer: bool = False,
        vibration: bool = True,
        duration_ms: int = 3000,
    ) -> dict[str, Any]:
        return {
            "warning_id": f"warning-{uuid.uuid4().hex[:8]}",
            "worker_id": worker_id,
            "warning_level": level,
            "actions": {"vibration": vibration, "buzzer": buzzer},
            "duration_ms": max(500, min(duration_ms, 10_000)),
            "reason": reason,
            "status": "PUBLISHED",
            "timestamp": datetime.now(UTC).isoformat(),
            "mqtt_topic": f"REKSA/helmet/{worker_id}/warning",
        }

