from app.schemas.risk import RiskContribution, RiskFeatures, RiskScoreResult

DEFAULT_WEIGHTS = {
    "hazard_exposure": 0.35,
    "near_miss_count": 0.20,
    "activity_risk": 0.15,
    "heat_exposure": 0.10,
    "work_duration": 0.10,
    "impact_status": 0.10,
}

RECOMMENDATIONS = {
    "SAFE": "Lanjutkan pemantauan normal.",
    "MODERATE": "Pantau posisi pekerja dan pergerakan bahaya.",
    "HIGH": "Peringatkan pekerja dan kurangi paparan bahaya.",
    "CRITICAL": "Hentikan aktivitas tidak aman, beri tahu supervisor, dan jauhkan pekerja.",
}


def classify_risk(score: int) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MODERATE"
    return "SAFE"


class RiskEngine:
    def __init__(self, scoring_profile: str | None = None) -> None:
        self.scoring_profile = scoring_profile or "default"

    def score(self, features: RiskFeatures) -> RiskScoreResult:
        normalized = {
            "hazard_exposure": features.hazard_exposure,
            "near_miss_count": min(features.near_miss_count / 5, 1),
            "activity_risk": features.activity_risk,
            "heat_exposure": features.heat_exposure,
            "work_duration": min(features.work_duration / 8, 1),
            "impact_status": float(features.impact_status),
        }
        contributions = {
            key: round(normalized[key] * weight * 100, 2)
            for key, weight in DEFAULT_WEIGHTS.items()
        }
        score = max(0, min(100, round(sum(contributions.values()))))
        level = classify_risk(score)

        explanation = [
            RiskContribution(factor=key, contribution=value)
            for key, value in sorted(contributions.items(), key=lambda item: item[1], reverse=True)
        ]
        return RiskScoreResult(
            risk_score=score,
            risk_level=level,
            risk_explanation=explanation,
            recommended_action=RECOMMENDATIONS[level],
            calculation_source="RULE_BASED_SCORING",
        )
