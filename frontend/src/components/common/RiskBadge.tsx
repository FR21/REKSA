import { AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react'
import { levelLabel } from '../../lib/utils'

export function RiskBadge({ level, compact = false }: { level: string; compact?: boolean }) {
  const Icon = level === 'SAFE' ? CheckCircle2 : level === 'CRITICAL' ? ShieldAlert : AlertTriangle
  return (
    <span className={`risk-badge risk-${level.toLowerCase()}`} aria-label={`Risiko ${levelLabel(level)}`}>
      <Icon size={compact ? 12 : 14} /> {!compact && levelLabel(level)}
    </span>
  )
}

