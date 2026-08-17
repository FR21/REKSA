from __future__ import annotations

import math
import statistics
from collections.abc import Iterable

from reksa_ai.contracts import ForecastRequest, SensorSample, TemporalFeatures, Zone

FORECAST_NUMERIC_FEATURES = [
    "window_duration_seconds",
    "sample_count",
    "rssi_mean",
    "rssi_peak",
    "rssi_min",
    "rssi_std",
    "rssi_slope",
    "warning_duration_seconds",
    "danger_duration_seconds",
    "state_transition_count",
    "packet_loss_ratio",
    "acceleration_mean_g",
    "acceleration_max_g",
    "acceleration_energy",
    "gyroscope_mean_dps",
    "gyroscope_max_dps",
    "gyroscope_energy",
    "orientation_change_deg",
    "sudden_motion",
    "hazard_active",
    "repeated_exposure_count",
]
FORECAST_CATEGORICAL_FEATURES = ["hazard_type"]
FORECAST_FEATURES = FORECAST_NUMERIC_FEATURES + FORECAST_CATEGORICAL_FEATURES

PRIORITY_NUMERIC_FEATURES = [
    "event_duration_seconds",
    "rssi_mean",
    "rssi_peak",
    "rssi_min",
    "rssi_std",
    "rssi_slope",
    "warning_duration_seconds",
    "danger_duration_seconds",
    "state_transition_count",
    "packet_loss_count",
    "acceleration_max_g",
    "gyroscope_max_dps",
    "orientation_change_deg",
    "sudden_motion",
    "candidate_impact",
    "candidate_fall",
    "post_event_stillness_seconds",
    "temperature_c",
    "humidity_percent",
    "mq135_deviation",
    "hazard_active",
    "local_warning_success",
    "repeated_exposure_count",
    "similar_event_count",
]
PRIORITY_CATEGORICAL_FEATURES = ["hazard_type", "alarm_level", "connectivity_status"]
PRIORITY_FEATURES = PRIORITY_NUMERIC_FEATURES + PRIORITY_CATEGORICAL_FEATURES


def magnitude(x: float, y: float, z: float) -> float:
    return math.sqrt(x * x + y * y + z * z)


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return statistics.fmean(items) if items else 0.0


def population_std(values: Iterable[float]) -> float:
    items = list(values)
    return statistics.pstdev(items) if len(items) > 1 else 0.0


def linear_slope(times: list[float], values: list[float]) -> float:
    if len(times) < 2 or len(set(times)) < 2:
        return 0.0
    time_mean = mean(times)
    value_mean = mean(values)
    numerator = sum((x - time_mean) * (y - value_mean) for x, y in zip(times, values, strict=True))
    denominator = sum((x - time_mean) ** 2 for x in times)
    return numerator / denominator if denominator else 0.0


def _zone_durations(samples: list[SensorSample]) -> tuple[float, float]:
    warning = 0.0
    danger = 0.0
    for current, following in zip(samples, samples[1:], strict=False):
        duration = max(0.0, (following.timestamp - current.timestamp).total_seconds())
        if current.proximity_level in {Zone.MODERATE, Zone.HIGH}:
            warning += duration
        elif current.proximity_level == Zone.CRITICAL:
            danger += duration
    return warning, danger


def extract_temporal_features(request: ForecastRequest) -> TemporalFeatures:
    samples = sorted(request.samples, key=lambda item: item.timestamp)
    start = samples[0].timestamp
    times = [(sample.timestamp - start).total_seconds() for sample in samples]

    valid_rssi = [
        (time, sample.rssi)
        for time, sample in zip(times, samples, strict=True)
        if sample.packet_received and sample.rssi is not None
    ]
    if len(valid_rssi) < 2:
        raise ValueError("at least two received BLE packets are required")
    rssi_times = [item[0] for item in valid_rssi]
    rssi_values = [float(item[1]) for item in valid_rssi]

    acceleration = [
        magnitude(sample.acceleration.x, sample.acceleration.y, sample.acceleration.z)
        for sample in samples
    ]
    gyroscope = [
        magnitude(sample.gyroscope.x, sample.gyroscope.y, sample.gyroscope.z)
        for sample in samples
    ]
    first_orientation = samples[0].orientation
    last_orientation = samples[-1].orientation
    orientation_change = magnitude(
        last_orientation.pitch - first_orientation.pitch,
        last_orientation.roll - first_orientation.roll,
        last_orientation.yaw - first_orientation.yaw,
    )
    warning_duration, danger_duration = _zone_durations(samples)
    transitions = sum(
        current.proximity_level != following.proximity_level
        for current, following in zip(samples, samples[1:], strict=False)
    )

    return TemporalFeatures(
        window_duration_seconds=max(0.0, times[-1]),
        sample_count=len(samples),
        rssi_mean=mean(rssi_values),
        rssi_peak=max(rssi_values),
        rssi_min=min(rssi_values),
        rssi_std=population_std(rssi_values),
        rssi_slope=linear_slope(rssi_times, rssi_values),
        warning_duration_seconds=warning_duration,
        danger_duration_seconds=danger_duration,
        state_transition_count=transitions,
        packet_loss_ratio=sum(not sample.packet_received for sample in samples) / len(samples),
        acceleration_mean_g=mean(acceleration),
        acceleration_max_g=max(acceleration),
        acceleration_energy=mean((value - 1.0) ** 2 for value in acceleration),
        gyroscope_mean_dps=mean(gyroscope),
        gyroscope_max_dps=max(gyroscope),
        gyroscope_energy=mean(value * value for value in gyroscope),
        orientation_change_deg=orientation_change,
        sudden_motion=max(acceleration) >= 2.5 or max(gyroscope) >= 180.0,
        hazard_active=any(sample.hazard_active for sample in samples),
        repeated_exposure_count=request.repeated_exposure_count,
        hazard_type=request.hazard_type.upper(),
    )
