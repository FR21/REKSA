from datetime import datetime, timedelta

from app.services.exposure_service import ExposureState


class NearMissService:
    def __init__(self, critical_duration: float = 5, cooldown_seconds: int = 30) -> None:
        self.critical_duration = critical_duration
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self._last_events: dict[str, datetime] = {}

    def should_create(
        self, key: str, exposure: ExposureState, hazard_status: str, now: datetime
    ) -> bool:
        if exposure.level != "CRITICAL":
            return False
        if hazard_status not in {"ACTIVE", "MOVING", "RUNNING"}:
            return False
        if exposure.duration_seconds < self.critical_duration:
            return False
        last_event = self._last_events.get(key)
        if last_event and now - last_event < self.cooldown:
            return False
        self._last_events[key] = now
        return True

