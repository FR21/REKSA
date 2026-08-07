export type RiskLevel = 'SAFE' | 'MODERATE' | 'HIGH' | 'CRITICAL'

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
  x: number
  y: number
  calculation_source: string
  dominant_factor: string
  recommended_action: string
}

export interface Hazard {
  id: string
  name: string
  type: string
  status: string
  online: boolean
  x: number
  y: number
  area: string
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
