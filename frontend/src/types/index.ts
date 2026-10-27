export type RiskLevel = 'SAFE' | 'MODERATE' | 'HIGH' | 'CRITICAL' | 'RECOVERY'

export interface OperationalAnomaly {
  engine: string
  window_id?: string
  worker_id?: string
  decision_score: number
  is_anomaly: boolean
  status: string
  alert_flag: string
  inference_source: string
  model_version: string
  advisory_only?: boolean
  generated_at?: string
}

export interface AIAdvisory {
  status: 'AWAITING_LIVE_TELEMETRY' | 'AWAITING_HAZARD' | 'COLLECTING_WINDOW' | 'READY' | 'UNAVAILABLE'
  escalation_probability?: number
  risk_level?: 'LOW' | 'MEDIUM' | 'HIGH'
  dominant_factors?: string[]
  recommendation?: string
  inference_source?: string
  model_version?: string
  probability_is_calibrated?: boolean
  score_semantics?: string
  sample_count?: number
  required_samples?: number
  generated_at: string
  advisory_only: true
  anomaly?: OperationalAnomaly
}


export interface Worker {
  id: string
  name: string
  role: string
  area: string
  risk_score: number
  risk_level: RiskLevel
  closest_hazard: string
  hazard_name: string
  hazard_type: string
  hazard_category?: 'MOBILE' | 'STATIONARY'
  hazard_status: string
  rssi: number
  smoothed_rssi: number
  proximity: RiskLevel
  exposure_seconds: number
  movement: string
  impact: boolean
  fall_detected: boolean
  impact_g: number
  mq135_raw: number
  air_quality_level: 'UNKNOWN' | 'NORMAL' | 'MODERATE' | 'POOR' | 'DANGEROUS'
  gas_alert: boolean
  temperature: number
  humidity: number
  online: boolean
  last_update: string
  x?: number
  y?: number
  calculation_source: string
  dominant_factor: string
  recommended_action: string
  ai_advisory: AIAdvisory
  recovery?: {
    active: boolean
    alarm_silenced?: boolean
    event_closed?: boolean
    safe_duration_seconds?: number
    note?: string
    closed_event_id?: string
  }
}

export interface Hazard {
  id: string
  name: string
  type: string
  category?: 'MOBILE' | 'STATIONARY'
  status: string
  online: boolean
  x?: number
  y?: number
  area: string
  beacon_name?: string
  alias?: string
  nearby_workers?: Worker[]
  exposure_count?: number
  near_miss_count?: number
}

export interface NearMiss {
  id: string
  timestamp: string
  worker_id: string
  worker_name: string
  hazard_id: string
  hazard_name: string
  hazard_type: string
  proximity: RiskLevel
  rssi: number
  duration: number
  hazard_status: string
  risk_score: number
  risk_level: RiskLevel
  warning_status: string
  acknowledged: boolean
  note: string
  acknowledged_by?: string
  acknowledged_at?: string
}

export interface Device {
  id: string
  type: string
  assignment: string
  online: boolean
  last_seen: string
  firmware: string
  signal: number
  topic: string
  latest_message: string
}

export interface HistoryPoint {
  date: string
  average_risk: number
  near_misses: number
  exposure_minutes: number
  temperature: number
  humidity: number
  uptime: number
  warning_latency: number
}

export interface VoiceTransmission {
  id: string
  timestamp: string
  worker_id: string
  worker_name: string
  worker_role?: string
  area: string
  transcription: string
  intent: 'EMERGENCY_EVACUATE' | 'ASSISTANCE_SOS' | 'MACHINE_HALT' | 'HAZARD_REPORT' | 'SAFETY_STATUS' | 'GENERAL_TRANSMISSION'
  intent_label: string
  urgency: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'INFO'
  nature: string
  confidence: number
  target_hazard_id?: string | null
  target_hazard_name?: string | null
  target_hazard_type?: string | null
  recommended_action: string
  acknowledged: boolean
  acknowledged_by?: string | null
  supervisor_note?: string
  action_taken?: string | null
  audio_available: boolean
  audio_url: string
  audio_data_uri?: string
  alarm_dispatched?: boolean
}

export interface UserProfile {
  name: string
  role: string
  initials: string
}
