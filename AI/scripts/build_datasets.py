#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from reksa_ai.datasets import (
    build_event_dataset,
    build_forecasting_windows,
    read_csv,
    write_csv,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build REKSA event-level AI datasets")
    parser.add_argument("raw_csv", type=Path)
    parser.add_argument("--forecast-output", type=Path, required=True)
    parser.add_argument("--event-output", type=Path, required=True)
    parser.add_argument("--window-seconds", type=float, default=10.0)
    parser.add_argument("--horizon-seconds", type=float, default=5.0)
    parser.add_argument("--step-seconds", type=float, default=1.0)
    parser.add_argument("--min-samples", type=int, default=4)
    args = parser.parse_args()

    raw = read_csv(args.raw_csv)
    windows = build_forecasting_windows(
        raw,
        window_seconds=args.window_seconds,
        horizon_seconds=args.horizon_seconds,
        step_seconds=args.step_seconds,
        min_samples=args.min_samples,
    )
    events = build_event_dataset(raw)
    write_csv(windows, args.forecast_output)
    write_csv(events, args.event_output)
    print(f"forecasting windows: {len(windows)} -> {args.forecast_output}")
    print(f"event records: {len(events)} -> {args.event_output}")


if __name__ == "__main__":
    main()

