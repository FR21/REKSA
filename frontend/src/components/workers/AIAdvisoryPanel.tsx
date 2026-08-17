import { Cpu } from 'lucide-react'
import type { AIAdvisory } from '../../types'
import { Panel } from '../common/Panel'

interface Props {
  advisory: AIAdvisory
  online: boolean
}

const FACTOR_LABELS: Record<string, string> = {
  rapid_rssi_increase: 'Pekerja mendekati hazard dengan cepat',
  strong_ble_proximity: 'Sinyal BLE menunjukkan jarak dekat',
  danger_zone_duration_high: 'Paparan zona bahaya cukup lama',
  sudden_motion: 'Gerakan mendadak terdeteksi',
  hazard_active: 'Hazard sedang aktif',
  repeated_exposure: 'Paparan berulang terdeteksi',
}

function waitingMessage(status: AIAdvisory['status']) {
  if (status === 'COLLECTING_WINDOW') return 'Mengumpulkan temporal window dari telemetry helm.'
  if (status === 'AWAITING_HAZARD') return 'Belum ada hazard aktif di sekitar pekerja.'
  if (status === 'UNAVAILABLE') return 'Layanan AI tidak tersedia. Safety rule lokal tetap aktif.'
  return 'Aktifkan telemetry helm fisik untuk menjalankan inference.'
}

export function AIAdvisoryPanel({ advisory, online }: Props) {
  const ready = advisory.status === 'READY' && advisory.escalation_probability !== undefined
  const percentage = ready ? Math.round(advisory.escalation_probability! * 100) : null
  const tone = advisory.risk_level === 'HIGH' ? 'critical' : advisory.risk_level === 'MEDIUM' ? 'high' : 'safe'
  const semantics = advisory.probability_is_calibrated ? 'Probabilitas terkalibrasi' : 'Skor advisory belum terkalibrasi'

  return (
    <Panel title="AI Early-Warning Advisory" subtitle="Prediksi pendekatan tidak aman 3-5 detik" className="action-panel">
      <div className={`recommendation risk-bg-${ready ? tone : 'safe'}`}>
        <Cpu size={32} />
        <div>
          <strong>{ready ? `${percentage}% · Advisory ${advisory.risk_level}` : 'Menunggu inference nyata'}</strong>
          <p>{ready ? advisory.recommendation : waitingMessage(advisory.status)}</p>
        </div>
      </div>
      {ready && advisory.dominant_factors && advisory.dominant_factors.length > 0 && (
        <p className="ai-reason-line">
          Faktor: {advisory.dominant_factors.map((factor) => FACTOR_LABELS[factor] ?? factor).join(' · ')}
        </p>
      )}
      <div className="source-line">
        <span>SUMBER INFERENCE</span>
        <b>{ready ? `${advisory.inference_source} · ${advisory.model_version} · ${semantics}` : `${advisory.status.replaceAll('_', ' ')} · ${online ? 'Safety rule aktif' : 'Perangkat offline'}`}</b>
      </div>
    </Panel>
  )
}
