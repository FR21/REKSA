from __future__ import annotations

from pathlib import Path
from typing import Any

from reksa_ai.artifacts import load_artifact
from reksa_ai.baselines import ForecastRuleBaseline, PriorityRuleBaseline
from reksa_ai.contracts import (
    AdvisoryLevel,
    AnomalyResponse,
    ForecastRequest,
    ForecastResponse,
    PriorityEvent,
    PriorityResponse,
    SupervisorPriority,
    TemporalFeatures,
)
from reksa_ai.features import PRIORITY_FEATURES, extract_temporal_features

ANOMALY_FEATURES = [
    "rssi_mean",
    "rssi_std",
    "rssi_slope",
    "packet_loss_ratio",
    "acceleration_mean_g",
    "acceleration_max_g",
    "acceleration_energy",
    "gyroscope_mean_dps",
    "gyroscope_max_dps",
    "gyroscope_energy",
    "orientation_change_deg",
    "warning_duration_seconds",
    "danger_duration_seconds",
    "state_transition_count",
]


def _dataframe(row: dict[str, Any], columns: list[str]) -> Any:
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pandas is required for trained-model inference") from exc
    return pd.DataFrame([{name: row.get(name) for name in columns}], columns=columns)


def _forecast_level(probability: float) -> AdvisoryLevel:
    if probability >= 0.70:
        return AdvisoryLevel.HIGH
    if probability >= 0.40:
        return AdvisoryLevel.MEDIUM
    return AdvisoryLevel.LOW


def _forecast_recommendation(level: AdvisoryLevel) -> str:
    if level == AdvisoryLevel.HIGH:
        return "Pantau perkembangan pola segera dan siapkan intervensi supervisor sesuai SOP."
    if level == AdvisoryLevel.MEDIUM:
        return "Tingkatkan pemantauan pekerja dan hazard; belum ada keputusan near-miss."
    return "Lanjutkan pemantauan normal melalui state machine keselamatan lokal."


def _priority_recommendation(priority: SupervisorPriority) -> str:
    if priority == SupervisorPriority.HIGH:
        return "Periksa event ini terlebih dahulu dan catat hasil verifikasi supervisor."
    if priority == SupervisorPriority.MEDIUM:
        return "Masukkan event ke antrean pemeriksaan pada shift berjalan."
    return "Simpan event untuk audit berkala; tetap dapat dinaikkan oleh supervisor."


def _priority_explanation(event: PriorityEvent, reasons: list[str]) -> str:
    phrases: list[str] = []
    if "danger_zone_duration_high" in reasons:
        phrases.append(f"durasi zona bahaya {event.danger_duration_seconds:.1f} detik")
    if "strong_ble_proximity" in reasons:
        phrases.append(f"peak RSSI {event.rssi_peak:.0f} dBm")
    if "sudden_motion" in reasons:
        phrases.append("terdapat gerakan mendadak")
    if "candidate_impact" in reasons:
        phrases.append("terdapat kandidat benturan")
    if "candidate_fall" in reasons:
        phrases.append("terdapat kandidat jatuh")
    if "repeated_exposure" in reasons:
        phrases.append(f"paparan berulang {event.repeated_exposure_count} kali")
    if "hazard_active" in reasons:
        phrases.append("hazard berstatus aktif")
    if not phrases:
        return "Indikator risiko utama pada event ini terbatas."
    return "Prioritas dihitung karena " + ", ".join(phrases) + "."


class NearMissRiskForecaster:
    def __init__(
        self,
        artifact_path: Path | None = None,
        *,
        anomaly_detector: OperationalAnomalyDetector | None = None,
    ) -> None:
        self.baseline = ForecastRuleBaseline()
        self.anomaly_detector = anomaly_detector
        self.bundle: dict[str, Any] | None = None
        self.load_error: str | None = None
        if artifact_path and artifact_path.exists():
            try:
                self.bundle = load_artifact(artifact_path, "near_miss_forecaster")
                if not self.bundle.get("deployment_recommended", False):
                    raise ValueError("artifact did not outperform its rule-based baseline")
            except Exception as exc:  # API remains available with an explicit fallback state
                self.bundle = None
                self.load_error = str(exc)

    def predict(self, request: ForecastRequest) -> ForecastResponse:
        features = extract_temporal_features(request)
        baseline_result = self.baseline.score(features)
        anomaly_result = (
            self.anomaly_detector.predict(request=request, features=features)
            if self.anomaly_detector
            else None
        )

        if self.bundle is None:
            source = "RULE_BASED_BASELINE" if self.load_error is None else "RULE_BASED_LOAD_FALLBACK"
            probability = baseline_result.score
            version = self.baseline.version
            calibrated = False
        else:
            row = features.model_dump(mode="json")
            columns = self.bundle["features"]
            probabilities = self.bundle["estimator"].predict_proba(_dataframe(row, columns))[0]
            classes = [str(value) for value in self.bundle["estimator"].classes_]
            positive_index = classes.index("1")
            probability = float(probabilities[positive_index])
            source = "TRAINED_MODEL"
            version = self.bundle["model_version"]
            calibrated = bool(self.bundle.get("probability_is_calibrated", False))

        level = _forecast_level(probability)
        return ForecastResponse(
            window_id=request.window_id,
            worker_id=request.worker_id,
            hazard_id=request.hazard_id,
            escalation_probability=round(probability, 4),
            risk_level=level,
            dominant_factors=baseline_result.reason_codes[:5],
            recommendation=_forecast_recommendation(level),
            inference_source=source,
            model_version=version,
            probability_is_calibrated=calibrated,
            score_semantics=(
                "CALIBRATED_PROBABILITY"
                if calibrated
                else "RULE_SCORE"
                if source.startswith("RULE_BASED")
                else "UNCALIBRATED_MODEL_SCORE"
            ),
            anomaly=anomaly_result,
        )


class PriorityEngine:
    def __init__(self, artifact_path: Path | None = None) -> None:
        self.baseline = PriorityRuleBaseline()
        self.bundle: dict[str, Any] | None = None
        self.load_error: str | None = None
        if artifact_path and artifact_path.exists():
            try:
                self.bundle = load_artifact(artifact_path, "priority_engine")
                if not self.bundle.get("deployment_recommended", False):
                    raise ValueError("artifact did not outperform its rule-based baseline")
            except Exception as exc:
                self.bundle = None
                self.load_error = str(exc)

    def predict(self, event: PriorityEvent) -> PriorityResponse:
        baseline_result = self.baseline.score(event)

        if self.bundle is None:
            source = "RULE_BASED_BASELINE" if self.load_error is None else "RULE_BASED_LOAD_FALLBACK"
            priority_score = round(baseline_result.score * 100)
            priority = self.baseline.priority(baseline_result.score)
            version = self.baseline.version
        else:
            raw = event.model_dump(mode="json")
            columns = self.bundle.get("features", PRIORITY_FEATURES)
            frame = _dataframe(raw, columns)
            probabilities = self.bundle["estimator"].predict_proba(frame)[0]
            classes = [str(value).upper() for value in self.bundle["estimator"].classes_]
            severity = {"LOW": 20, "MEDIUM": 55, "HIGH": 90}
            priority_score = round(
                sum(float(probability) * severity[label] for probability, label in zip(probabilities, classes, strict=True))
            )
            priority = SupervisorPriority(classes[max(range(len(classes)), key=lambda i: probabilities[i])])
            source = "TRAINED_MODEL"
            version = self.bundle["model_version"]

        return PriorityResponse(
            event_id=event.event_id,
            worker_id=event.worker_id,
            priority=priority,
            priority_score=priority_score,
            reason_codes=baseline_result.reason_codes[:6],
            explanation=_priority_explanation(event, baseline_result.reason_codes),
            recommended_action=_priority_recommendation(priority),
            inference_source=source,
            model_version=version,
        )


class OperationalAnomalyDetector:
    def __init__(self, artifact_path: Path | None = None) -> None:
        self.bundle: dict[str, Any] | None = None
        self.load_error: str | None = None
        if artifact_path and artifact_path.exists():
            try:
                self.bundle = load_artifact(artifact_path, "operational_anomaly_detector")
            except Exception as exc:
                self.bundle = None
                self.load_error = str(exc)

    def predict(
        self,
        request: ForecastRequest | None = None,
        features: TemporalFeatures | None = None,
    ) -> AnomalyResponse:
        if features is None:
            if request is None:
                raise ValueError("request or features must be provided")
            features = extract_temporal_features(request)

        window_id = request.window_id if request else None
        worker_id = request.worker_id if request else None

        if self.bundle is None:
            is_anomaly = features.packet_loss_ratio > 0.4 or features.acceleration_max_g > 4.0
            score = -0.1 if is_anomaly else 0.1
            source = "RULE_BASED_BASELINE" if self.load_error is None else "RULE_BASED_LOAD_FALLBACK"
            version = "anomaly-rule-v1"
        else:
            raw = features.model_dump(mode="json")
            columns = self.bundle.get("features", ANOMALY_FEATURES)
            frame = _dataframe(raw, columns)
            estimator = self.bundle["estimator"]
            score = float(estimator.decision_function(frame)[0])
            pred = int(estimator.predict(frame)[0])
            is_anomaly = pred == -1
            source = "TRAINED_MODEL"
            version = self.bundle.get("model_version", "anomaly-v1")

        return AnomalyResponse(
            window_id=window_id,
            worker_id=worker_id,
            decision_score=round(score, 4),
            is_anomaly=is_anomaly,
            status="ANOMALY_DETECTED" if is_anomaly else "NORMAL",
            alert_flag="FLAG_ANOMALOUS_TELEMETRY" if is_anomaly else "FLAG_NORMAL",
            inference_source=source,
            model_version=version,
        )
