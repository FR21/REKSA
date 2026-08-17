export type AiAdvisoryLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export interface NearMissForecast {
  engine: 'NEAR_MISS_RISK_FORECASTER'
  window_id: string
  worker_id: string
  hazard_id: string
  escalation_probability: number
  risk_level: AiAdvisoryLevel
  dominant_factors: string[]
  explanation_method: 'THRESHOLD_REASON_CODES'
  recommendation: string
  inference_source: 'TRAINED_MODEL' | 'RULE_BASED_BASELINE' | 'RULE_BASED_LOAD_FALLBACK'
  model_version: string
  probability_is_calibrated: boolean
  score_semantics: 'CALIBRATED_PROBABILITY' | 'UNCALIBRATED_MODEL_SCORE' | 'RULE_SCORE'
  advisory_only: true
  generated_at: string
}

export interface EventPriorityAssessment {
  engine: 'AI_PRIORITY_ENGINE'
  event_id: string
  worker_id: string
  priority: AiAdvisoryLevel
  priority_score: number
  reason_codes: string[]
  explanation: string
  explanation_method: 'THRESHOLD_REASON_CODES'
  recommended_action: string
  inference_source: 'TRAINED_MODEL' | 'RULE_BASED_BASELINE' | 'RULE_BASED_LOAD_FALLBACK'
  model_version: string
  advisory_only: true
  requires_supervisor_verification: true
  generated_at: string
}
