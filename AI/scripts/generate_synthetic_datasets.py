#!/usr/bin/env python3
"""Generate reproducible synthetic datasets for the two REKSA AI engines.

The generated records imitate controlled safety scenarios. They are useful for
pipeline development and model prototyping, but are not evidence of real-world
performance and are never labeled as verified near-miss records.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Scenario:
    weight: float
    rssi_mean: float
    rssi_std: float
    rssi_slope: float
    warning_duration: float
    danger_duration: float
    acceleration_mean: float
    acceleration_max: float
    gyroscope_mean: float
    gyroscope_max: float
    orientation_change: float
    sudden_motion_probability: float
    hazard_active_probability: float
    repeated_exposure_mean: float
    packet_loss_mean: float
    escalation_bias: float


SCENARIOS: dict[str, Scenario] = {
    "NORMAL_PASSAGE": Scenario(
        0.19, -82, 2.5, 0.2, 1.2, 0.0, 1.03, 1.25, 12, 45, 8, 0.03, 0.75, 0.3, 0.03, -2.2
    ),
    "NORMAL_WORK_NEAR_MACHINE": Scenario(
        0.14, -74, 3.0, 0.0, 4.5, 0.2, 1.06, 1.35, 16, 55, 10, 0.05, 0.90, 1.2, 0.04, -1.4
    ),
    "RSSI_FLUCTUATION": Scenario(
        0.09, -72, 8.0, 0.3, 3.0, 0.5, 1.05, 1.30, 14, 50, 9, 0.04, 0.80, 0.8, 0.08, -1.1
    ),
    "FORKLIFT_APPROACH": Scenario(
        0.12, -67, 4.0, 2.6, 4.0, 1.2, 1.12, 1.70, 28, 95, 18, 0.18, 0.96, 1.6, 0.04, 0.6
    ),
    "FORKLIFT_CROSSING": Scenario(
        0.09, -63, 4.5, 1.3, 3.5, 2.1, 1.18, 2.10, 40, 135, 25, 0.30, 0.98, 1.9, 0.05, 1.1
    ),
    "PROLONGED_DANGER": Scenario(
        0.07, -58, 3.5, 0.5, 2.0, 5.6, 1.10, 1.65, 25, 90, 16, 0.12, 0.99, 2.7, 0.04, 1.8
    ),
    "SUDDEN_MOTION_AFTER_WARNING": Scenario(
        0.07, -62, 4.0, 1.8, 3.0, 2.8, 1.35, 3.20, 75, 230, 42, 0.86, 0.97, 2.0, 0.05, 1.7
    ),
    "IMPACT_CANDIDATE": Scenario(
        0.05, -65, 4.5, 0.9, 2.5, 2.0, 1.55, 4.80, 90, 300, 55, 0.94, 0.92, 1.5, 0.06, 1.9
    ),
    "FALL_CANDIDATE": Scenario(
        0.04, -66, 5.0, 0.7, 2.2, 2.1, 1.42, 3.80, 105, 350, 75, 0.96, 0.90, 1.3, 0.07, 2.0
    ),
    "REPEATED_EXPOSURE": Scenario(
        0.05, -64, 4.0, 0.8, 4.0, 2.6, 1.14, 1.90, 34, 115, 22, 0.22, 0.96, 5.2, 0.05, 1.3
    ),
    "HAZARD_INACTIVE": Scenario(
        0.04, -61, 4.0, 0.4, 3.0, 1.3, 1.07, 1.45, 18, 65, 12, 0.06, 0.05, 0.7, 0.04, -2.0
    ),
    "BLE_PACKET_LOSS": Scenario(
        0.03, -73, 6.0, 0.2, 2.0, 0.4, 1.08, 1.50, 20, 75, 14, 0.10, 0.85, 1.0, 0.32, -0.9
    ),
    "AIR_QUALITY_DEGRADATION": Scenario(
        0.02, -77, 3.0, 0.1, 1.5, 0.2, 1.05, 1.35, 15, 55, 10, 0.05, 0.75, 0.6, 0.05, -0.7
    ),
}

HAZARDS = [
    ("F01", "FORKLIFT"),
    ("F02", "FORKLIFT"),
    ("F03", "FORKLIFT"),
    ("G01", "GRINDING_MACHINE"),
    ("L01", "LASER_CUTTER"),
]

VERIFICATION_BY_SCENARIO = {
    "NORMAL_PASSAGE": "SYNTHETIC_NORMAL_ACTIVITY",
    "NORMAL_WORK_NEAR_MACHINE": "SYNTHETIC_NORMAL_ACTIVITY",
    "RSSI_FLUCTUATION": "SYNTHETIC_FALSE_ALARM",
    "FORKLIFT_APPROACH": "SIMULATED_UNSAFE_PROXIMITY",
    "FORKLIFT_CROSSING": "SIMULATED_HIGH_RISK",
    "PROLONGED_DANGER": "SIMULATED_HIGH_RISK",
    "SUDDEN_MOTION_AFTER_WARNING": "SIMULATED_HIGH_RISK",
    "IMPACT_CANDIDATE": "SIMULATED_IMPACT_CANDIDATE",
    "FALL_CANDIDATE": "SIMULATED_FALL_CANDIDATE",
    "REPEATED_EXPOSURE": "SIMULATED_REPEATED_EXPOSURE",
    "HAZARD_INACTIVE": "SYNTHETIC_HAZARD_INACTIVE",
    "BLE_PACKET_LOSS": "SYNTHETIC_INSUFFICIENT_EVIDENCE",
    "AIR_QUALITY_DEGRADATION": "SIMULATED_ENVIRONMENTAL_RISK",
}


def clip(value: float, lower: float, upper: float) -> float:
    return float(np.clip(value, lower, upper))


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-clip(value, -30, 30)))


def scenario_choice(rng: np.random.Generator) -> tuple[str, Scenario]:
    names = list(SCENARIOS)
    probabilities = np.array([SCENARIOS[name].weight for name in names], dtype=float)
    probabilities /= probabilities.sum()
    name = str(rng.choice(names, p=probabilities))
    return name, SCENARIOS[name]


def identity_for_row(
    index: int,
    *,
    participant_count: int,
    sessions_per_participant: int,
    start_date: datetime,
) -> dict[str, Any]:
    participant_number = index % participant_count + 1
    session_number = (index // participant_count) % sessions_per_participant + 1
    day_offset = (participant_number * 3 + session_number * 7) % 90
    recording_date = (start_date + timedelta(days=day_offset)).date().isoformat()
    return {
        "participant_id": f"P{participant_number:03d}",
        "session_id": f"S{session_number:02d}",
        "recording_date": recording_date,
    }


def participant_effects(participant_count: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    return {
        "rssi": rng.normal(0, 2.0, participant_count),
        "motion": rng.normal(0, 0.10, participant_count),
        "risk": rng.normal(0, 0.28, participant_count),
        "temperature": rng.normal(0, 0.5, participant_count),
    }


def recording_timestamp(
    identity: dict[str, Any], group_sequence: int, *, spacing_seconds: int
) -> datetime:
    recording_day = datetime.fromisoformat(identity["recording_date"]).replace(tzinfo=UTC)
    session_number = int(str(identity["session_id"])[1:])
    return recording_day + timedelta(
        hours=6 + session_number,
        seconds=group_sequence * spacing_seconds,
    )


def build_forecasting_dataset(
    row_count: int,
    participant_count: int,
    sessions_per_participant: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    start_date = datetime(2026, 1, 5, tzinfo=UTC)
    effects = participant_effects(participant_count, rng)

    for index in range(row_count):
        identity = identity_for_row(
            index,
            participant_count=participant_count,
            sessions_per_participant=sessions_per_participant,
            start_date=start_date,
        )
        participant_index = int(identity["participant_id"][1:]) - 1
        scenario_name, scenario = scenario_choice(rng)
        session_noise = rng.normal(0, 0.8)
        hazard_id, hazard_type = HAZARDS[int(rng.integers(0, len(HAZARDS)))]
        if scenario_name.startswith("FORKLIFT"):
            hazard_id, hazard_type = HAZARDS[int(rng.integers(0, 3))]

        window_duration = clip(rng.normal(10.0, 0.35), 8.0, 12.0)
        packet_loss_ratio = clip(rng.normal(scenario.packet_loss_mean, 0.035), 0.0, 0.65)
        nominal_samples = int(round(window_duration * rng.choice([5, 8, 10], p=[0.2, 0.5, 0.3])))
        sample_count = max(10, nominal_samples)

        rssi_mean = clip(
            rng.normal(
                scenario.rssi_mean + effects["rssi"][participant_index] + session_noise,
                2.2,
            ),
            -105,
            -42,
        )
        rssi_std = clip(rng.normal(scenario.rssi_std, 1.1), 0.4, 16.0)
        rssi_peak = clip(rssi_mean + abs(rng.normal(rssi_std * 1.25 + 1.0, 1.1)), -100, -35)
        rssi_min = clip(rssi_mean - abs(rng.normal(rssi_std * 1.25 + 1.0, 1.1)), -120, -40)
        rssi_slope = clip(rng.normal(scenario.rssi_slope, 0.75), -5.0, 8.0)

        warning_duration = clip(rng.normal(scenario.warning_duration, 0.9), 0, window_duration)
        danger_duration = clip(rng.normal(scenario.danger_duration, 0.75), 0, window_duration)
        if warning_duration + danger_duration > window_duration:
            warning_duration = max(0.0, window_duration - danger_duration)
        transition_count = int(clip(rng.poisson(1.0 + rssi_std / 4.0), 0, 12))

        acceleration_mean = clip(
            rng.normal(scenario.acceleration_mean + effects["motion"][participant_index], 0.08),
            0.75,
            2.8,
        )
        acceleration_max = clip(
            rng.normal(scenario.acceleration_max + effects["motion"][participant_index], 0.30),
            acceleration_mean,
            8.0,
        )
        acceleration_energy = clip(
            (acceleration_max - 1.0) ** 2 * rng.uniform(0.15, 0.55)
            + rng.normal(0.03, 0.02),
            0,
            15,
        )
        gyroscope_mean = clip(rng.normal(scenario.gyroscope_mean, 7), 0, 300)
        gyroscope_max = clip(
            rng.normal(scenario.gyroscope_max, 22), gyroscope_mean, 700
        )
        gyroscope_energy = clip(
            gyroscope_max**2 * rng.uniform(0.08, 0.30), 0, 150000
        )
        orientation_change = clip(rng.normal(scenario.orientation_change, 8), 0, 180)
        sudden_probability = clip(
            scenario.sudden_motion_probability
            + 0.08 * (acceleration_max >= 2.5)
            + 0.06 * (gyroscope_max >= 180),
            0,
            0.99,
        )
        sudden_motion = bool(rng.random() < sudden_probability)
        hazard_active = bool(rng.random() < scenario.hazard_active_probability)
        repeated_exposure = int(
            clip(rng.poisson(scenario.repeated_exposure_mean), 0, 12)
        )

        logit = (
            -4.3
            + scenario.escalation_bias
            + 0.34 * danger_duration
            + 0.055 * (rssi_peak + 80)
            + 0.20 * max(0.0, rssi_slope)
            + 0.72 * sudden_motion
            + 0.11 * repeated_exposure
            + 0.45 * hazard_active
            + effects["risk"][participant_index]
            + rng.normal(0, 0.65)
        )
        escalation_probability = sigmoid(logit)
        target = int(rng.random() < escalation_probability)

        group_sequence = index // (participant_count * sessions_per_participant)
        window_start = recording_timestamp(identity, group_sequence, spacing_seconds=2)
        trajectory_number = group_sequence // 5 + 1
        rows.append(
            {
                "window_id": f"WIN-{index + 1:07d}",
                **identity,
                "scenario_id": scenario_name,
                "trajectory_id": f"TRJ-{identity['participant_id']}-{identity['session_id']}-{trajectory_number:06d}",
                "worker_id": f"W{participant_index % 20 + 1:02d}",
                "hazard_id": hazard_id,
                "window_started_at": window_start.isoformat(),
                "window_ended_at": (window_start + timedelta(seconds=window_duration)).isoformat(),
                "window_duration_seconds": round(window_duration, 3),
                "sample_count": sample_count,
                "rssi_mean": round(rssi_mean, 3),
                "rssi_peak": round(rssi_peak, 3),
                "rssi_min": round(rssi_min, 3),
                "rssi_std": round(rssi_std, 3),
                "rssi_slope": round(rssi_slope, 4),
                "warning_duration_seconds": round(warning_duration, 3),
                "danger_duration_seconds": round(danger_duration, 3),
                "state_transition_count": transition_count,
                "packet_loss_ratio": round(packet_loss_ratio, 4),
                "acceleration_mean_g": round(acceleration_mean, 4),
                "acceleration_max_g": round(acceleration_max, 4),
                "acceleration_energy": round(acceleration_energy, 4),
                "gyroscope_mean_dps": round(gyroscope_mean, 3),
                "gyroscope_max_dps": round(gyroscope_max, 3),
                "gyroscope_energy": round(gyroscope_energy, 3),
                "orientation_change_deg": round(orientation_change, 3),
                "sudden_motion": sudden_motion,
                "hazard_active": hazard_active,
                "repeated_exposure_count": repeated_exposure,
                "hazard_type": hazard_type,
                "escalated_within_horizon": target,
                "target_source": "SYNTHETIC_CONTROLLED_SCENARIO",
                "data_origin": "SYNTHETIC",
            }
        )
    return pd.DataFrame(rows)


def alarm_level(rssi_peak: float, danger_duration: float, hazard_active: bool) -> str:
    if hazard_active and (danger_duration >= 3.5 or rssi_peak >= -57):
        return "CRITICAL"
    if hazard_active and (danger_duration >= 1.0 or rssi_peak >= -67):
        return "HIGH"
    if rssi_peak >= -78:
        return "MODERATE"
    return "SAFE"


def build_priority_dataset(
    row_count: int,
    participant_count: int,
    sessions_per_participant: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    start_date = datetime(2026, 1, 5, tzinfo=UTC)
    effects = participant_effects(participant_count, rng)

    for index in range(row_count):
        identity = identity_for_row(
            index,
            participant_count=participant_count,
            sessions_per_participant=sessions_per_participant,
            start_date=start_date,
        )
        participant_index = int(identity["participant_id"][1:]) - 1
        scenario_name, scenario = scenario_choice(rng)
        hazard_id, hazard_type = HAZARDS[int(rng.integers(0, len(HAZARDS)))]
        if scenario_name.startswith("FORKLIFT"):
            hazard_id, hazard_type = HAZARDS[int(rng.integers(0, 3))]

        rssi_mean = clip(
            rng.normal(scenario.rssi_mean + effects["rssi"][participant_index], 2.4),
            -110,
            -40,
        )
        rssi_std = clip(rng.normal(scenario.rssi_std, 1.2), 0.4, 18)
        rssi_peak = clip(rssi_mean + abs(rng.normal(rssi_std * 1.4 + 1, 1.3)), -105, -34)
        rssi_min = clip(rssi_mean - abs(rng.normal(rssi_std * 1.4 + 1, 1.3)), -120, -40)
        rssi_slope = clip(rng.normal(scenario.rssi_slope, 0.9), -6, 9)

        warning_duration = clip(rng.normal(scenario.warning_duration * 1.5, 1.3), 0, 20)
        danger_duration = clip(rng.normal(scenario.danger_duration * 1.4, 1.0), 0, 20)
        event_duration = clip(
            warning_duration + danger_duration + abs(rng.normal(1.8, 1.0)), 0.5, 30
        )
        if warning_duration + danger_duration > event_duration:
            event_duration = warning_duration + danger_duration

        acceleration_max = clip(
            rng.normal(scenario.acceleration_max + effects["motion"][participant_index], 0.35),
            0.8,
            9.0,
        )
        gyroscope_max = clip(rng.normal(scenario.gyroscope_max, 28), 0, 800)
        orientation_change = clip(rng.normal(scenario.orientation_change, 10), 0, 180)
        sudden_motion = bool(
            rng.random()
            < clip(
                scenario.sudden_motion_probability
                + 0.12 * (acceleration_max >= 2.5)
                + 0.08 * (gyroscope_max >= 180),
                0,
                0.99,
            )
        )
        candidate_impact = bool(
            rng.random()
            < (0.80 if scenario_name == "IMPACT_CANDIDATE" else 0.035 + 0.10 * sudden_motion)
        )
        candidate_fall = bool(
            rng.random()
            < (0.82 if scenario_name == "FALL_CANDIDATE" else 0.018 + 0.05 * sudden_motion)
        )
        stillness = clip(
            rng.normal(
                6.5 if candidate_fall else 2.8 if candidate_impact else 0.5,
                1.5,
            ),
            0,
            20,
        )
        hazard_active = bool(rng.random() < scenario.hazard_active_probability)
        repeated_exposure = int(clip(rng.poisson(scenario.repeated_exposure_mean), 0, 15))
        packet_loss_count = int(clip(rng.poisson(scenario.packet_loss_mean * 20), 0, 20))
        transition_count = int(clip(rng.poisson(1.0 + rssi_std / 3.5), 0, 15))

        temperature = clip(
            rng.normal(30.0 + effects["temperature"][participant_index], 2.3), 20, 47
        )
        humidity = clip(rng.normal(66, 8), 25, 98)
        mq135_deviation = clip(
            rng.normal(900 if scenario_name == "AIR_QUALITY_DEGRADATION" else 120, 170),
            -250,
            1800,
        )
        local_warning_success = bool(rng.random() >= 0.015 + packet_loss_count * 0.004)
        connectivity_status = (
            "DEGRADED" if packet_loss_count >= 6 else "OFFLINE" if not local_warning_success and rng.random() < 0.2 else "ONLINE"
        )
        level = alarm_level(rssi_peak, danger_duration, hazard_active)

        latent_score = (
            7
            + 22 * clip(danger_duration / 7, 0, 1)
            + 17 * clip((rssi_peak + 90) / 40, 0, 1)
            + 10 * sudden_motion
            + 20 * (candidate_impact or candidate_fall)
            + 9 * clip(repeated_exposure / 6, 0, 1)
            + 6 * hazard_active
            + 4 * clip(transition_count / 6, 0, 1)
            + 3 * (not local_warning_success)
            + 4 * clip(stillness / 8, 0, 1)
            + 3 * clip(max(0.0, mq135_deviation) / 1000, 0, 1)
            + effects["risk"][participant_index] * 5
            + rng.normal(0, 8.0)
        )
        latent_score = clip(latent_score, 0, 100)
        if latent_score >= 70:
            priority = "HIGH"
        elif latent_score >= 40:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        group_sequence = index // (participant_count * sessions_per_participant)
        occurred_at = recording_timestamp(identity, group_sequence, spacing_seconds=180)
        rows.append(
            {
                "event_id": f"EVT-SYN-{index + 1:07d}",
                **identity,
                "scenario_id": scenario_name,
                "worker_id": f"W{participant_index % 20 + 1:02d}",
                "helmet_id": f"HELMET-W{participant_index % 20 + 1:02d}",
                "hazard_id": hazard_id,
                "hazard_type": hazard_type,
                "occurred_at": occurred_at.isoformat(),
                "event_duration_seconds": round(event_duration, 3),
                "rssi_mean": round(rssi_mean, 3),
                "rssi_peak": round(rssi_peak, 3),
                "rssi_min": round(rssi_min, 3),
                "rssi_std": round(rssi_std, 3),
                "rssi_slope": round(rssi_slope, 4),
                "warning_duration_seconds": round(warning_duration, 3),
                "danger_duration_seconds": round(danger_duration, 3),
                "state_transition_count": transition_count,
                "packet_loss_count": packet_loss_count,
                "acceleration_max_g": round(acceleration_max, 4),
                "gyroscope_max_dps": round(gyroscope_max, 3),
                "orientation_change_deg": round(orientation_change, 3),
                "sudden_motion": sudden_motion,
                "candidate_impact": candidate_impact,
                "candidate_fall": candidate_fall,
                "post_event_stillness_seconds": round(stillness, 3),
                "temperature_c": round(temperature, 3),
                "humidity_percent": round(humidity, 3),
                "mq135_deviation": round(mq135_deviation, 3),
                "hazard_active": hazard_active,
                "alarm_level": level,
                "local_warning_success": local_warning_success,
                "repeated_exposure_count": repeated_exposure,
                "similar_event_count": int(clip(rng.poisson(repeated_exposure / 2), 0, 12)),
                "connectivity_status": connectivity_status,
                "supervisor_priority": priority,
                "verification_label": VERIFICATION_BY_SCENARIO[scenario_name],
                "label_source": "SYNTHETIC_SCENARIO_POLICY_WITH_NOISE",
                "data_origin": "SYNTHETIC",
            }
        )
    return pd.DataFrame(rows)


def validate_forecasting(frame: pd.DataFrame) -> dict[str, bool]:
    return {
        "unique_window_id": bool(frame["window_id"].is_unique),
        "no_missing_values": bool(not frame.isna().any().any()),
        "recording_date_matches_timestamp": bool(
            (
                pd.to_datetime(frame["window_started_at"], utc=True).dt.date.astype(str)
                == frame["recording_date"]
            ).all()
        ),
        "rssi_order_valid": bool(
            ((frame["rssi_min"] <= frame["rssi_mean"]) & (frame["rssi_mean"] <= frame["rssi_peak"])).all()
        ),
        "durations_fit_window": bool(
            (
                frame["warning_duration_seconds"]
                + frame["danger_duration_seconds"]
                <= frame["window_duration_seconds"] + 0.001
            ).all()
        ),
        "binary_target": bool(set(frame["escalated_within_horizon"]) == {0, 1}),
        "synthetic_origin_only": bool((frame["data_origin"] == "SYNTHETIC").all()),
    }


def validate_priority(frame: pd.DataFrame) -> dict[str, bool]:
    return {
        "unique_event_id": bool(frame["event_id"].is_unique),
        "no_missing_values": bool(not frame.isna().any().any()),
        "recording_date_matches_timestamp": bool(
            (
                pd.to_datetime(frame["occurred_at"], utc=True).dt.date.astype(str)
                == frame["recording_date"]
            ).all()
        ),
        "rssi_order_valid": bool(
            ((frame["rssi_min"] <= frame["rssi_mean"]) & (frame["rssi_mean"] <= frame["rssi_peak"])).all()
        ),
        "durations_fit_event": bool(
            (
                frame["warning_duration_seconds"]
                + frame["danger_duration_seconds"]
                <= frame["event_duration_seconds"] + 0.001
            ).all()
        ),
        "all_priority_classes": bool(
            set(frame["supervisor_priority"]) == {"LOW", "MEDIUM", "HIGH"}
        ),
        "no_verified_near_miss_claim": bool(
            ~frame["verification_label"].str.contains("VERIFIED_NEAR_MISS").any()
        ),
        "synthetic_origin_only": bool((frame["data_origin"] == "SYNTHETIC").all()),
    }


def distribution(frame: pd.DataFrame, column: str) -> dict[str, int]:
    return {str(key): int(value) for key, value in frame[column].value_counts().items()}


def build_report(
    forecast: pd.DataFrame,
    priority: pd.DataFrame,
    *,
    seed: int,
) -> dict[str, Any]:
    forecast_checks = validate_forecasting(forecast)
    priority_checks = validate_priority(priority)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "generator_seed": seed,
        "warning": (
            "SYNTHETIC DATA ONLY. Suitable for pipeline development and prototyping; "
            "not valid evidence of real-world safety performance."
        ),
        "forecasting_windows": {
            "rows": len(forecast),
            "participants": int(forecast["participant_id"].nunique()),
            "participant_session_groups": int(
                forecast[["participant_id", "session_id"]].drop_duplicates().shape[0]
            ),
            "target_distribution": distribution(forecast, "escalated_within_horizon"),
            "participants_with_both_targets": int(
                (forecast.groupby("participant_id")["escalated_within_horizon"].nunique() == 2).sum()
            ),
            "scenario_distribution": distribution(forecast, "scenario_id"),
            "checks": forecast_checks,
        },
        "priority_events": {
            "rows": len(priority),
            "participants": int(priority["participant_id"].nunique()),
            "participant_session_groups": int(
                priority[["participant_id", "session_id"]].drop_duplicates().shape[0]
            ),
            "priority_distribution": distribution(priority, "supervisor_priority"),
            "participants_with_all_priority_classes": int(
                (priority.groupby("participant_id")["supervisor_priority"].nunique() == 3).sum()
            ),
            "verification_distribution": distribution(priority, "verification_label"),
            "scenario_distribution": distribution(priority, "scenario_id"),
            "checks": priority_checks,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic REKSA AI datasets")
    parser.add_argument("--output-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--forecast-rows", type=int, default=15000)
    parser.add_argument("--priority-rows", type=int, default=6000)
    parser.add_argument("--participants", type=int, default=40)
    parser.add_argument("--sessions", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    if min(args.forecast_rows, args.priority_rows, args.participants, args.sessions) <= 0:
        parser.error("row, participant, and session counts must be positive")

    seed_sequence = np.random.SeedSequence(args.seed)
    forecast_rng, priority_rng = [np.random.default_rng(seed) for seed in seed_sequence.spawn(2)]
    forecast = build_forecasting_dataset(
        args.forecast_rows, args.participants, args.sessions, forecast_rng
    )
    priority = build_priority_dataset(
        args.priority_rows, args.participants, args.sessions, priority_rng
    )
    report = build_report(forecast, priority, seed=args.seed)
    checks = [
        *report["forecasting_windows"]["checks"].values(),
        *report["priority_events"]["checks"].values(),
    ]
    if not all(checks):
        failed = {
            "forecasting": report["forecasting_windows"]["checks"],
            "priority": report["priority_events"]["checks"],
        }
        raise RuntimeError(f"synthetic dataset validation failed: {failed}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    forecast_path = args.output_dir / "forecasting_windows_synthetic.csv"
    priority_path = args.output_dir / "event_dataset_synthetic.csv"
    report_path = args.output_dir / "synthetic_dataset_report.json"
    forecast.to_csv(forecast_path, index=False)
    priority.to_csv(priority_path, index=False)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"forecasting dataset: {len(forecast):,} rows -> {forecast_path}")
    print(f"priority dataset:    {len(priority):,} rows -> {priority_path}")
    print(f"quality report:      {report_path}")
    print(json.dumps({
        "forecast_target": report["forecasting_windows"]["target_distribution"],
        "priority_target": report["priority_events"]["priority_distribution"],
    }, indent=2))


if __name__ == "__main__":
    main()
