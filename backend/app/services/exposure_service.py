from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExposureState:
    started_at: datetime
    last_seen_at: datetime
    readings: list[float]
    level: str

    @property
    def duration_seconds(self) -> float:
        return max(0.0, (self.last_seen_at - self.started_at).total_seconds())


class ExposureService:
    def __init__(self) -> None:
        self.active: dict[str, ExposureState] = {}

    def update(self, key: str, level: str, rssi: float, timestamp: datetime) -> ExposureState | None:
        if level == "SAFE":
            return self.active.pop(key, None)
        state = self.active.get(key)
        if state is None:
            state = ExposureState(timestamp, timestamp, [rssi], level)
            self.active[key] = state
        else:
            state.last_seen_at = timestamp
            state.readings.append(rssi)
            state.level = level
        return state

