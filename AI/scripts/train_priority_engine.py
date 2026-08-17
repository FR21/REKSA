#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reksa_ai.training import train_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the REKSA AI Priority Engine")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("models/priority_engine.joblib"))
    parser.add_argument("--version", default="priority-v1")
    parser.add_argument("--test-size", type=float, default=0.25)
    args = parser.parse_args()
    result = train_engine(
        args.dataset,
        args.output,
        kind="priority_engine",
        model_version=args.version,
        test_size=args.test_size,
    )
    print(json.dumps(result.__dict__, indent=2, default=str))


if __name__ == "__main__":
    main()

