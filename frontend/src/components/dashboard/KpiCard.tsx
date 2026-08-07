import type { LucideIcon } from 'lucide-react'

export function KpiCard({ label, value, unit, detail, icon: Icon, tone = 'blue' }: { label: string; value: string | number; unit?: string; detail: string; icon: LucideIcon; tone?: string }) {
  return <div className={`kpi-card tone-${tone}`}><div className="kpi-top"><span>{label}</span><div className="kpi-icon"><Icon size={18} /></div></div><div className="kpi-value">{value}<small>{unit}</small></div><p>{detail}</p></div>
}

