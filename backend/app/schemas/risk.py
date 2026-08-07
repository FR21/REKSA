from pydantic import BaseModel, Field


class RiskFeatures(BaseModel):
    hazard_exposure: float = Field(ge=0, le=1)
    near_miss_count: int = Field(ge=0)
    activity_risk: float = Field(ge=0, le=1)
    heat_exposure: float = Field(ge=0, le=1)
    work_duration: float = Field(ge=0, le=24)
    impact_status: bool


class RiskContribution(BaseModel):
    factor: str
    contribution: float


class RiskScoreResult(BaseModel):
    risk_score: int
    risk_level: str
    risk_explanation: list[RiskContribution]
    recommended_action: str
    calculation_source: str
