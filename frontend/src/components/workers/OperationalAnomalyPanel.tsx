import { Activity, AlertTriangle, CheckCircle2, WifiOff } from 'lucide-react'
import type { OperationalAnomaly } from '../../types'
import { Panel } from '../common/Panel'
import { useTranslation } from '../../i18n'

interface Props {
  anomaly?: OperationalAnomaly
  online: boolean
  impactG?: number
  rssi?: number
}

export function OperationalAnomalyPanel({ anomaly, online, impactG, rssi }: Props) {
  const { t } = useTranslation()

  if (!online) {
    return (
      <Panel
        title={t.aiAdvisory.anomalyTitle}
        subtitle={t.aiAdvisory.anomalySubtitle}
        className="action-panel"
      >
        <div className="recommendation risk-bg-standby">
          <WifiOff size={32} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
              <strong>{t.aiAdvisory.anomalyOfflineTitle}</strong>
              <span className="anomaly-score-tag">
                Offline
              </span>
            </div>
            <p>{t.aiAdvisory.anomalyOfflineDesc}</p>
          </div>
        </div>

        <div className="ai-factor-pills">
          {t.aiAdvisory.anomalyOfflinePills.map((pill) => (
            <span key={pill} className="ai-factor-pill">
              {pill}
            </span>
          ))}
        </div>

        <div className="source-line">
          <span>{t.aiAdvisory.sourceTitle}</span>
          <b>{t.aiAdvisory.anomalyOfflineSource}</b>
        </div>
      </Panel>
    )
  }

  const hasAnomaly = Boolean(anomaly)
  const isAnomaly = Boolean(anomaly?.is_anomaly)

  const tone = !online ? 'standby' : isAnomaly ? 'critical' : hasAnomaly ? 'safe' : 'standby'

  const currentG = impactG !== undefined && impactG !== null ? impactG : 1.0
  const currentRssi = rssi !== undefined && rssi !== null ? rssi : -75

  const scoreFormatted = anomaly
    ? anomaly.decision_score > 0
      ? `+${anomaly.decision_score.toFixed(3)}`
      : anomaly.decision_score.toFixed(3)
    : null

  return (
    <Panel
      title={t.aiAdvisory.anomalyTitle}
      subtitle={t.aiAdvisory.anomalySubtitle}
      className="action-panel"
    >
      <div className={`recommendation risk-bg-${tone}`}>
        {isAnomaly ? (
          <AlertTriangle size={32} />
        ) : hasAnomaly ? (
          <CheckCircle2 size={32} />
        ) : (
          <Activity size={32} />
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
            <strong>
              {isAnomaly
                ? t.aiAdvisory.anomalyDetected
                : hasAnomaly
                ? t.aiAdvisory.anomalyNormal
                : t.aiAdvisory.anomalyAwaiting}
            </strong>
            {scoreFormatted !== null && (
              <span className="anomaly-score-tag">
                {t.aiAdvisory.anomalyScoreLabel}: {scoreFormatted}
              </span>
            )}
          </div>
          <p>
            {isAnomaly
              ? t.aiAdvisory.anomalyDetectedDesc
              : hasAnomaly
              ? t.aiAdvisory.anomalyNormalDesc
              : t.aiAdvisory.anomalyStandbyDesc}
          </p>
        </div>
      </div>

      {/* 2. Sensor Diagnostic Badges */}
      <div className="ai-factor-pills">
        <span className="ai-factor-pill">
          {isAnomaly ? t.aiAdvisory.telemetryAnomalyIMU(currentG) : t.aiAdvisory.telemetryHealthyIMU(currentG)}
        </span>
        <span className="ai-factor-pill">
          {isAnomaly ? t.aiAdvisory.telemetryAnomalySignal(currentRssi) : t.aiAdvisory.telemetryHealthySignal(currentRssi)}
        </span>
        <span className="ai-factor-pill">
          {isAnomaly ? t.aiAdvisory.telemetryPacketLossWarning : t.aiAdvisory.telemetryPacketLossNormal}
        </span>
      </div>

      <div className="source-line">
        <span>{t.aiAdvisory.sourceTitle}</span>
        <b>{t.aiAdvisory.mlModel}</b>
      </div>
    </Panel>
  )
}
