#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path


def percentile(values: list[int], probability: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize REKSA firmware timing evidence")
    parser.add_argument("serial_log", type=Path)
    args = parser.parse_args()

    pending_transition: int | None = None
    latencies: list[int] = []
    alarm_events = 0
    offline_alarm_events = 0
    for raw in args.serial_log.read_text(encoding="utf-8", errors="replace").splitlines():
        marker = raw.find("METRIC,")
        if marker < 0:
            continue
        parts = raw[marker:].split(",")
        if len(parts) >= 6 and parts[1] == "ZONE_TRANSITION" and parts[4] in {"HIGH", "CRITICAL"}:
            pending_transition = int(parts[5])
        elif len(parts) >= 6 and parts[1] == "ALARM_APPLIED" and int(parts[2]) >= 3:
            alarm_events += 1
            applied_at = int(parts[3])
            if "wifi=0" in parts or "mqtt=0" in parts:
                offline_alarm_events += 1
            if pending_transition is not None and applied_at >= pending_transition:
                latencies.append(applied_at - pending_transition)
                pending_transition = None

    print(f"alarm_events={alarm_events}")
    print(f"offline_alarm_events={offline_alarm_events}")
    print(f"paired_latency_samples={len(latencies)}")
    print(f"warning_latency_p50_ms={percentile(latencies, 0.50)}")
    print(f"warning_latency_p95_ms={percentile(latencies, 0.95)}")
    print(f"warning_latency_max_ms={max(latencies) if latencies else None}")


if __name__ == "__main__":
    main()
