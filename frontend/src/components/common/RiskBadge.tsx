import { AlertTriangle, CheckCircle2, ShieldAlert, ShieldCheck } from 'lucide-react'
import { levelLabel } from '../../lib/utils'
import { useTranslation } from '../../i18n'

export function RiskBadge({ level, compact = false }: { level: string; compact?: boolean }) {
  const { language } = useTranslation()

  const Icon =
    level === 'SAFE'
      ? CheckCircle2
      : level === 'RECOVERY'
      ? ShieldCheck
      : level === 'CRITICAL'
      ? ShieldAlert
      : AlertTriangle
  const label = levelLabel(level, language)
  const ariaLabel = language === 'en' ? `Risk ${label}` : `Risiko ${label}`

  return (
    <span className={`risk-badge risk-${level.toLowerCase()}`} aria-label={ariaLabel}>
      <Icon size={compact ? 12 : 14} /> {!compact && label}
    </span>
  )
}
