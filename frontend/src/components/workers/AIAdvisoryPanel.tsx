import { Cpu } from 'lucide-react'
import type { AIAdvisory } from '../../types'
import { Panel } from '../common/Panel'
import { useTranslation } from '../../i18n'

interface Props {
  advisory: AIAdvisory
  online: boolean
}

export function AIAdvisoryPanel({ advisory, online }: Props) {
  const { t } = useTranslation()

  function waitingMessage(status: AIAdvisory['status']) {
    if (status === 'COLLECTING_WINDOW') return t.aiAdvisory.statusCollecting
    if (status === 'AWAITING_HAZARD') return t.aiAdvisory.statusAwaiting
    if (status === 'UNAVAILABLE') return t.aiAdvisory.statusUnavailable
    return t.aiAdvisory.statusPhysical
  }

  const ready = advisory.status === 'READY' && advisory.escalation_probability !== undefined
  const percentage = ready ? Math.round(advisory.escalation_probability! * 100) : null
  const tone = advisory.risk_level === 'HIGH' ? 'critical' : advisory.risk_level === 'MEDIUM' ? 'high' : 'safe'
  const semantics = advisory.probability_is_calibrated ? t.aiAdvisory.calibrated : t.aiAdvisory.uncalibrated

  return (
    <Panel title={t.aiAdvisory.title} subtitle={t.aiAdvisory.subtitle} className="action-panel">
      <div className={`recommendation risk-bg-${ready ? tone : 'safe'}`}>
        <Cpu size={32} />
        <div>
          <strong>{ready ? `${percentage}% · Advisory ${advisory.risk_level}` : t.aiAdvisory.awaitingInference}</strong>
          <p>{ready ? advisory.recommendation : waitingMessage(advisory.status)}</p>
        </div>
      </div>
      {ready && advisory.dominant_factors && advisory.dominant_factors.length > 0 && (
        <p className="ai-reason-line">
          {t.aiAdvisory.factorsPrefix} {advisory.dominant_factors.map((factor) => t.aiAdvisory.factorLabels[factor] ?? factor).join(' · ')}
        </p>
      )}
      <div className="source-line">
        <span>{t.aiAdvisory.sourceTitle}</span>
        <b>
          {ready
            ? `${advisory.inference_source} · ${advisory.model_version} · ${semantics}`
            : `${advisory.status.replaceAll('_', ' ')} · ${online ? t.aiAdvisory.safetyRuleActive : t.aiAdvisory.deviceOffline}`}
        </b>
      </div>
    </Panel>
  )
}
