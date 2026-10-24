import { AlertTriangle, Cpu, Radio, WifiOff } from 'lucide-react'
import type { AIAdvisory } from '../../types'
import { Panel } from '../common/Panel'
import { useTranslation } from '../../i18n'

interface Props {
  advisory: AIAdvisory
  online: boolean
}

export function AIAdvisoryPanel({ advisory, online }: Props) {
  const { t } = useTranslation()

  if (!online) {
    return (
      <Panel title={t.aiAdvisory.title} subtitle={t.aiAdvisory.subtitle} className="action-panel">
        <div className="recommendation risk-bg-standby">
          <WifiOff size={32} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <strong>{t.aiAdvisory.offlineTitle}</strong>
            <p>{t.aiAdvisory.offlineDesc}</p>
          </div>
        </div>

        <div className="ai-factor-pills">
          {t.aiAdvisory.offlinePills.map((pill) => (
            <span key={pill} className="ai-factor-pill">
              {pill}
            </span>
          ))}
        </div>

        <div className="source-line">
          <span>{t.aiAdvisory.sourceTitle}</span>
          <b>{t.aiAdvisory.offlineSource}</b>
        </div>
      </Panel>
    )
  }

  function waitingMessage(status: AIAdvisory['status']) {
    if (status === 'COLLECTING_WINDOW') return t.aiAdvisory.statusCollecting
    if (status === 'AWAITING_HAZARD') return t.aiAdvisory.statusAwaiting
    if (status === 'UNAVAILABLE') return t.aiAdvisory.statusUnavailable
    return t.aiAdvisory.statusPhysical
  }

  const ready = advisory.status === 'READY' && advisory.escalation_probability !== undefined
  const percentage = ready ? Math.round(advisory.escalation_probability! * 100) : null
  const tone = advisory.risk_level === 'HIGH' ? 'critical' : advisory.risk_level === 'MEDIUM' ? 'high' : 'safe'

  return (
    <Panel title={t.aiAdvisory.title} subtitle={t.aiAdvisory.subtitle} className="action-panel">
      {/* 1. Main Recommendation Block */}
      <div className={`recommendation risk-bg-${ready ? tone : 'standby'}`}>
        {ready ? (
          tone === 'critical' ? <AlertTriangle size={32} /> : <Cpu size={32} />
        ) : (
          <Radio size={32} />
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <strong>
            {ready
              ? `${percentage}% · Advisory ${advisory.risk_level}`
              : t.aiAdvisory.awaitingInference}
          </strong>
          <p>
            {ready
              ? (t.aiAdvisory.aiRecommendations[advisory.recommendation ?? ''] ?? advisory.recommendation)
              : waitingMessage(advisory.status)}
          </p>
        </div>
      </div>

      {/* 2. Dominant Threat Factors as Clean Pill Badges */}
      {ready && advisory.dominant_factors && advisory.dominant_factors.length > 0 && (
        <div className="ai-factor-pills">
          {advisory.dominant_factors.map((factor) => (
            <span key={factor} className="ai-factor-pill">
              {t.aiAdvisory.factorLabels[factor] ?? factor}
            </span>
          ))}
        </div>
      )}

      {/* 3. Footer */}
      <div className="source-line">
        <span>{t.aiAdvisory.sourceTitle}</span>
        <b>{ready ? t.aiAdvisory.mlModel : t.aiAdvisory.safetyProtocol}</b>
      </div>
    </Panel>
  )
}



