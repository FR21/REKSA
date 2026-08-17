from datetime import datetime, timedelta


def is_device_offline(last_seen: datetime | None, now: datetime, timeout_seconds: int) -> bool:
    if last_seen is None:
        return True
    return now - last_seen > timedelta(seconds=timeout_seconds)

