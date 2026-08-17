#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reksa_ai.training import train_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the REKSA Near-Miss Risk Forecaster")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("models/near_miss_forecaster.joblib"))
    parser.add_argument("--version", default="forecaster-v1")
    parser.add_argument("--test-size", type=float, default=0.25)
    args = parser.parse_args()
    result = train_engine(
        args.dataset,
        args.output,
        kind="near_miss_forecaster",
        model_version=args.version,
        test_size=args.test_size,
    )
    print(json.dumps(result.__dict__, indent=2, default=str))


if __name__ == "__main__":
    main()

