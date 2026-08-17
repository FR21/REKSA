from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def save_artifact(bundle: dict[str, Any], output_path: Path) -> Path:
    try:
        import joblib
    except ImportError as exc:  # pragma: no cover - dependency message for operators
        raise RuntimeError("joblib is required to save model artifacts") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output_path)
    metadata = {key: value for key, value in bundle.items() if key != "estimator"}
    metadata["artifact_path"] = output_path.name
    output_path.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return output_path


def load_artifact(path: Path, expected_kind: str) -> dict[str, Any]:
    try:
        import joblib
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("joblib is required to load trained models") from exc

    bundle = joblib.load(path)
    if not isinstance(bundle, dict) or "estimator" not in bundle:
        raise ValueError(f"invalid model artifact: {path}")
    if bundle.get("kind") != expected_kind:
        raise ValueError(
            f"artifact kind {bundle.get('kind')!r} does not match {expected_kind!r}"
        )
    return bundle


def new_bundle(
    *,
    kind: str,
    estimator: Any,
    model_version: str,
    features: list[str],
    metrics: dict[str, Any],
    probability_is_calibrated: bool,
    classes: list[str | int],
    dataset_rows: int,
    deployment_recommended: bool,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "model_version": model_version,
        "estimator": estimator,
        "features": features,
        "metrics": metrics,
        "probability_is_calibrated": probability_is_calibrated,
        "classes": classes,
        "dataset_rows": dataset_rows,
        "deployment_recommended": deployment_recommended,
        "trained_at": datetime.now(UTC).isoformat(),
    }
