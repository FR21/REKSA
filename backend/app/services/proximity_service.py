from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class ProximityThresholds:
    moderate: float = -70
    high: float = -60
    critical: float = -45
    hysteresis: float = 2
    window_size: int = 5
    consecutive_readings: int = 2


class ProximityService:
    levels = ("SAFE", "MODERATE", "HIGH", "CRITICAL")

    def __init__(self, thresholds: ProximityThresholds | None = None) -> None:
        self.thresholds = thresholds or ProximityThresholds()
        self._windows: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.thresholds.window_size)
        )
        self._stable_levels: dict[str, str] = {}
        self._candidates: dict[str, tuple[str, int]] = {}

    @staticmethod
    def is_valid_rssi(value: float) -> bool:
        return -120 <= value <= 0

    def classify(self, value: float | None) -> str:
        if value is None or not self.is_valid_rssi(value):
            return "SAFE"
        if value >= self.thresholds.critical:
            return "CRITICAL"
        if value >= self.thresholds.high:
            return "HIGH"
        if value >= self.thresholds.moderate:
            return "MODERATE"
        return "SAFE"

    def add_reading(self, key: str, raw_rssi: float) -> tuple[float, str]:
        if not self.is_valid_rssi(raw_rssi):
            stable = self._stable_levels.get(key, "SAFE")
            window = self._windows.get(key)
            average = sum(window) / len(window) if window else -120.0
            return round(average, 2), stable

        window = self._windows[key]
        window.append(raw_rssi)
        smoothed = sum(window) / len(window)
        candidate = self.classify(smoothed)
        stable = self._stable_levels.get(key, "SAFE")

        if candidate == stable:
            self._candidates.pop(key, None)
            return round(smoothed, 2), stable

        # A downward transition waits until it passes the boundary plus hysteresis.
        if self.levels.index(candidate) < self.levels.index(stable):
            boundary = {
                "MODERATE": self.thresholds.moderate,
                "HIGH": self.thresholds.high,
                "CRITICAL": self.thresholds.critical,
            }.get(stable, -120)
            if smoothed >= boundary - self.thresholds.hysteresis:
                return round(smoothed, 2), stable

        last_candidate, count = self._candidates.get(key, (candidate, 0))
        count = count + 1 if last_candidate == candidate else 1
        self._candidates[key] = (candidate, count)
        if count >= self.thresholds.consecutive_readings:
            self._stable_levels[key] = candidate
            self._candidates.pop(key, None)
            stable = candidate
        return round(smoothed, 2), stable

