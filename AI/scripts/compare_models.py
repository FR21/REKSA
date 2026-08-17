#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def render(metadata: dict[str, Any]) -> str:
    metrics = metadata["metrics"]
    split = metrics["split_policy"]
    lines = [
        f"# Model evidence: {metadata['kind']}",
        "",
        f"- Model version: `{metadata['model_version']}`",
        f"- Dataset rows: {metadata['dataset_rows']}",
        f"- Held-out groups: {split['test_groups']} (grouped by {', '.join(split['group_columns'])})",
        f"- Probability calibrated: {metadata['probability_is_calibrated']}",
        f"- Deployment recommended: **{metadata['deployment_recommended']}**",
        "",
        "## Held-out comparison",
        "",
    ]
    for name, values in metrics["candidate_test_metrics"].items():
        compact = ", ".join(
            f"{key}={value:.4f}"
            for key, value in values.items()
            if isinstance(value, int | float)
        )
        lines.append(f"- `{name}`: {compact}")
    selected = metrics["selected_test_metrics"]
    lines.extend(["", "## Selected model", ""])
    lines.append(
        ", ".join(
            f"{key}={value:.4f}"
            for key, value in selected.items()
            if isinstance(value, int | float)
        )
    )
    lines.extend(["", f"> {metrics['warning']}", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate auditable REKSA model evidence")
    parser.add_argument("metadata", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, default=Path("models/model-evidence.md"))
    args = parser.parse_args()
    sections = [render(json.loads(path.read_text(encoding="utf-8"))) for path in args.metadata]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(sections), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
