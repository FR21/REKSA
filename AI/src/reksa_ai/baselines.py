from __future__ import annotations

from dataclasses import dataclass

from reksa_ai.contracts import PriorityEvent, SupervisorPriority, TemporalFeatures, Zone


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def proximity_severity(rssi_peak: float) -> float:
    """Normalize RSSI from weak (-90 dBm) to very strong (-50 dBm)."""
    return clamp((rssi_peak + 90.0) / 40.0)


@dataclass(frozen=True)
class RuleResult:
    score: float
    reason_codes: list[str]


class ForecastRuleBaseline:
    """Cold-start baseline; its score is not a calibrated probability."""

    version = "forecast-rule-v1"

    def score(self, features: TemporalFeatures) -> RuleResult:
        reasons: list[str] = []
        score = 0.03
        score += 0.25 * clamp(features.danger_duration_seconds / 5.0)
        score += 0.18 * proximity_severity(features.rssi_peak)
        score += 0.14 * clamp(max(0.0, features.rssi_slope) / 6.0)
        score += 0.13 * float(features.sudden_motion)
        score += 0.08 * clamp((features.acceleration_max_g - 1.0) / 3.0)
        score += 0.09 * clamp(features.repeated_exposure_count / 5.0)
        score += 0.07 * float(features.hazard_active)
        score += 0.03 * clamp(features.packet_loss_ratio / 0.4)

        if features.danger_duration_seconds >= 3.0:
            reasons.append("danger_zone_duration_high")
        if features.rssi_peak >= -65:
            reasons.append("strong_ble_proximity")
        if features.rssi_slope >= 2.0:
            reasons.append("rapid_rssi_increase")
        if features.sudden_motion:
            reasons.append("sudden_motion")
        if features.repeated_exposure_count >= 2:
            reasons.append("repeated_exposure")
        if features.hazard_active:
            reasons.append("hazard_active")
        if features.packet_loss_ratio >= 0.25:
            reasons.append("ble_packet_loss_high")
        if not reasons:
            reasons.append("no_dominant_risk_pattern")

        return RuleResult(score=clamp(score, maximum=0.95), reason_codes=reasons)


class PriorityRuleBaseline:
    version = "priority-rule-v1"

    def score(self, event: PriorityEvent) -> RuleResult:
        reasons: list[str] = []
        score = 5.0
        score += 23.0 * clamp(event.danger_duration_seconds / 5.0)
        score += 18.0 * proximity_severity(event.rssi_peak)
        score += 10.0 * float(event.sudden_motion)
        score += 20.0 * float(event.candidate_impact or event.candidate_fall)
        score += 10.0 * clamp(event.repeated_exposure_count / 5.0)
        score += 7.0 * float(event.hazard_active)
        score += 4.0 * clamp(event.state_transition_count / 5.0)
        score += 3.0 * float(not event.local_warning_success)
        score += 3.0 * clamp(event.post_event_stillness_seconds / 10.0)
        if event.mq135_deviation is not None:
            score += 2.0 * clamp(max(0.0, event.mq135_deviation) / 1000.0)

        if event.danger_duration_seconds >= 3.0:
            reasons.append("danger_zone_duration_high")
        if event.rssi_peak >= -65:
            reasons.append("strong_ble_proximity")
        if event.sudden_motion:
            reasons.append("sudden_motion")
        if event.candidate_impact:
            reasons.append("candidate_impact")
        if event.candidate_fall:
            reasons.append("candidate_fall")
        if event.post_event_stillness_seconds >= 3.0:
            reasons.append("post_event_stillness")
        if event.repeated_exposure_count >= 2:
            reasons.append("repeated_exposure")
        if event.hazard_active:
            reasons.append("hazard_active")
        if not event.local_warning_success:
            reasons.append("local_warning_not_confirmed")
        if event.alarm_level == Zone.CRITICAL:
            reasons.append("critical_local_alarm")
        if not reasons:
            reasons.append("limited_risk_indicators")

        return RuleResult(score=clamp(score / 100.0), reason_codes=reasons)

    @staticmethod
    def priority(score: float) -> SupervisorPriority:
        if score >= 0.70:
            return SupervisorPriority.HIGH
        if score >= 0.40:
            return SupervisorPriority.MEDIUM
        return SupervisorPriority.LOW

