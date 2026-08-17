from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from reksa_ai.contracts import ForecastRequest, Orientation, SensorSample, Vector3, Zone
from reksa_ai.features import extract_temporal_features, magnitude

RAW_REQUIRED_COLUMNS = {
    "participant_id",
    "session_id",
    "scenario_id",
    "trajectory_id",
    "timestamp",
    "worker_id",
    "helmet_id",
    "hazard_id",
    "hazard_type",
    "rssi",
    "packet_received",
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "pitch",
    "roll",
    "yaw",
    "proximity_level",
    "hazard_active",
    "forecast_target",
}


def _truthy(value: Any) -> bool:
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _optional_float(value: Any) -> float | None:
    return None if pd.isna(value) or str(value).strip() == "" else float(value)


def _mode_or_default(values: Iterable[Any], default: str = "") -> str:
    cleaned = [str(value).strip() for value in values if not pd.isna(value) and str(value).strip()]
    if not cleaned:
        return default
    return max(set(cleaned), key=cleaned.count)


def _column_mean(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(values.mean()) if not values.empty else None


def validate_raw_samples(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(RAW_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"raw dataset is missing columns: {', '.join(missing)}")
    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True, errors="raise")
    duplicate_mask = result.duplicated(subset=["trajectory_id", "timestamp"])
    if duplicate_mask.any():
        duplicate_count = int(duplicate_mask.sum())
        raise ValueError(
            f"raw dataset contains {duplicate_count} duplicate trajectory timestamps"
        )
    return result.sort_values(["trajectory_id", "timestamp"]).reset_index(drop=True)


def _sample_from_row(row: pd.Series) -> SensorSample:
    packet_received = _truthy(row["packet_received"])
    return SensorSample(
        timestamp=row["timestamp"].to_pydatetime(),
        rssi=_optional_float(row["rssi"]) if packet_received else None,
        packet_received=packet_received,
        acceleration=Vector3(x=row["accel_x"], y=row["accel_y"], z=row["accel_z"]),
        gyroscope=Vector3(x=row["gyro_x"], y=row["gyro_y"], z=row["gyro_z"]),
        orientation=Orientation(pitch=row["pitch"], roll=row["roll"], yaw=row["yaw"]),
        proximity_level=Zone(str(row["proximity_level"]).upper()),
        hazard_active=_truthy(row["hazard_active"]),
    )


def _request_from_window(window_id: str, frame: pd.DataFrame) -> ForecastRequest:
    first = frame.iloc[0]
    repeated = int(frame["repeated_exposure_count"].max()) if "repeated_exposure_count" in frame else 0
    return ForecastRequest(
        window_id=window_id,
        worker_id=str(first["worker_id"]),
        helmet_id=str(first["helmet_id"]),
        hazard_id=str(first["hazard_id"]),
        hazard_type=str(first["hazard_type"]),
        repeated_exposure_count=repeated,
        samples=[_sample_from_row(row) for _, row in frame.iterrows()],
    )


def build_forecasting_windows(
    raw: pd.DataFrame,
    *,
    window_seconds: float = 10.0,
    horizon_seconds: float = 5.0,
    step_seconds: float = 1.0,
    min_samples: int = 4,
) -> pd.DataFrame:
    """Build features using only samples at or before each window end.

    The target is 1 only when a labeled escalation occurs strictly after the window end
    and within the configured forecast horizon. ``target_source`` preserves whether the
    label came from a controlled scenario or supervisor verification.
    """
    frame = validate_raw_samples(raw)
    output: list[dict[str, Any]] = []

    for trajectory_id, trajectory in frame.groupby("trajectory_id", sort=False):
        trajectory = trajectory.sort_values("timestamp")
        first_time = trajectory["timestamp"].min()
        final_time = trajectory["timestamp"].max()
        window_end = first_time + pd.Timedelta(seconds=window_seconds)
        sequence = 0

        while window_end + pd.Timedelta(seconds=horizon_seconds) <= final_time:
            window_start = window_end - pd.Timedelta(seconds=window_seconds)
            window = trajectory[
                (trajectory["timestamp"] > window_start)
                & (trajectory["timestamp"] <= window_end)
            ]
            future = trajectory[
                (trajectory["timestamp"] > window_end)
                & (
                    trajectory["timestamp"]
                    <= window_end + pd.Timedelta(seconds=horizon_seconds)
                )
            ]
            if len(window) >= min_samples:
                request = _request_from_window(f"{trajectory_id}-{sequence:05d}", window)
                try:
                    features = extract_temporal_features(request).model_dump(mode="json")
                except ValueError:
                    window_end += pd.Timedelta(seconds=step_seconds)
                    sequence += 1
                    continue
                first = window.iloc[0]
                output.append(
                    {
                        "window_id": request.window_id,
                        "participant_id": first["participant_id"],
                        "session_id": first["session_id"],
                        "scenario_id": first["scenario_id"],
                        "trajectory_id": trajectory_id,
                        "worker_id": first["worker_id"],
                        "hazard_id": first["hazard_id"],
                        "window_started_at": window_start.isoformat(),
                        "window_ended_at": window_end.isoformat(),
                        **features,
                        "escalated_within_horizon": int(
                            future["forecast_target"].map(_truthy).any()
                        ),
                        "target_source": _mode_or_default(
                            future.get("target_source", []), "UNSPECIFIED"
                        ),
                    }
                )
            window_end += pd.Timedelta(seconds=step_seconds)
            sequence += 1

    return pd.DataFrame(output)


def build_event_dataset(raw: pd.DataFrame) -> pd.DataFrame:
    frame = validate_raw_samples(raw)
    if "event_id" not in frame.columns:
        raise ValueError("raw dataset is missing event_id")
    events = frame[frame["event_id"].fillna("").astype(str).str.strip() != ""]
    output: list[dict[str, Any]] = []
    zone_rank = {Zone.SAFE: 0, Zone.MODERATE: 1, Zone.HIGH: 2, Zone.CRITICAL: 3}

    for event_id, event in events.groupby("event_id", sort=False):
        event = event.sort_values("timestamp")
        request = _request_from_window(str(event_id), event)
        try:
            temporal = extract_temporal_features(request)
        except ValueError:
            continue
        first = event.iloc[0]
        acceleration_max = max(
            magnitude(row.accel_x, row.accel_y, row.accel_z)
            for row in event.itertuples(index=False)
        )
        gyroscope_max = max(
            magnitude(row.gyro_x, row.gyro_y, row.gyro_z)
            for row in event.itertuples(index=False)
        )
        levels = [Zone(str(value).upper()) for value in event["proximity_level"]]
        alarm_level = max(levels, key=zone_rank.get)

        output.append(
            {
                "event_id": event_id,
                "participant_id": first["participant_id"],
                "session_id": first["session_id"],
                "scenario_id": first["scenario_id"],
                "worker_id": first["worker_id"],
                "helmet_id": first["helmet_id"],
                "hazard_id": first["hazard_id"],
                "hazard_type": first["hazard_type"],
                "occurred_at": event["timestamp"].min().isoformat(),
                "event_duration_seconds": temporal.window_duration_seconds,
                "rssi_mean": temporal.rssi_mean,
                "rssi_peak": temporal.rssi_peak,
                "rssi_min": temporal.rssi_min,
                "rssi_std": temporal.rssi_std,
                "rssi_slope": temporal.rssi_slope,
                "warning_duration_seconds": temporal.warning_duration_seconds,
                "danger_duration_seconds": temporal.danger_duration_seconds,
                "state_transition_count": temporal.state_transition_count,
                "packet_loss_count": int((~event["packet_received"].map(_truthy)).sum()),
                "acceleration_max_g": acceleration_max,
                "gyroscope_max_dps": gyroscope_max,
                "orientation_change_deg": temporal.orientation_change_deg,
                "sudden_motion": temporal.sudden_motion,
                "candidate_impact": event.get("candidate_impact", pd.Series(False, index=event.index)).map(_truthy).any(),
                "candidate_fall": event.get("candidate_fall", pd.Series(False, index=event.index)).map(_truthy).any(),
                "post_event_stillness_seconds": _column_mean(event, "post_event_stillness_seconds") or 0.0,
                "temperature_c": _column_mean(event, "temperature_c"),
                "humidity_percent": _column_mean(event, "humidity_percent"),
                "mq135_deviation": _column_mean(event, "mq135_deviation"),
                "hazard_active": temporal.hazard_active,
                "alarm_level": alarm_level.value,
                "local_warning_success": "local_warning_success" not in event or event["local_warning_success"].map(_truthy).all(),
                "repeated_exposure_count": temporal.repeated_exposure_count,
                "similar_event_count": int(event.get("similar_event_count", pd.Series(0, index=event.index)).max()),
                "connectivity_status": _mode_or_default(event.get("connectivity_status", []), "ONLINE"),
                "supervisor_priority": _mode_or_default(event.get("supervisor_priority", [])),
                "verification_label": _mode_or_default(event.get("verification_label", [])),
            }
        )
    return pd.DataFrame(output)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path
