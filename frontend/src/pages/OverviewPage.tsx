import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Cpu, Gauge, RadioTower, ShieldCheck, Siren, Timer, Users } from 'lucide-react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../services/api'
import type { Hazard, HistoryPoint, Worker } from '../types'
import { useLiveStore } from '../stores/liveStore'
import { KpiCard } from '../components/dashboard/KpiCard'
import { Panel } from '../components/common/Panel'
import { RiskBadge } from '../components/common/RiskBadge'
import { ErrorState, LoadingState } from '../components/common/States'
import { formatDate } from '../lib/utils'
import { useProfile } from '../hooks/useProfile'
import { useTranslation } from '../i18n'

interface Summary { active_workers: number; total_workers: number; active_hazards: number; high_risk_workers: number; critical_risk_workers: number; near_misses_today: number; average_risk_score: number; connected_devices: number; total_devices: number; average_warning_latency: number }
interface LiveData { workers: Worker[]; critical_alerts: Worker[]; risk_distribution: Record<string, number>; hazards: Hazard[] }

export default function OverviewPage() {
  const { t, language } = useTranslation()
  const { firstName } = useProfile()
  const summary = useQuery({ queryKey: ['summary'], queryFn: () => api<Summary>('/dashboard/summary'), refetchInterval: 10_000 })
  const live = useQuery({ queryKey: ['dashboard-live'], queryFn: () => api<LiveData>('/dashboard/live') })
  const history = useQuery({ queryKey: ['risk-trend', '7d'], queryFn: () => api<{ items: HistoryPoint[] }>('/analytics/risk-trend?period=7d') })
  const activities = useQuery({ queryKey: ['activity'], queryFn: () => api<{ items: { id: string; type: string; message: string; timestamp: string }[] }>('/dashboard/activity') })
  const workers = useLiveStore((state) => state.workers)
  const setWorkers = useLiveStore((state) => state.setWorkers)
  useEffect(() => { if (live.data?.workers && workers.length === 0) setWorkers(live.data.workers) }, [live.data, setWorkers, workers.length])

  if (summary.isLoading || live.isLoading) return <LoadingState label={t.common.loading} />
  if (summary.isError || live.isError || !summary.data || !live.data) return <ErrorState retry={() => { void summary.refetch(); void live.refetch() }} />
  const activeWorkers = (workers.length ? workers : live.data.workers).filter((worker) => worker.online)
  const critical = activeWorkers.filter((worker) => worker.risk_level === 'CRITICAL')
  const distribution = ['SAFE', 'MODERATE', 'HIGH', 'CRITICAL'].map((name) => ({ name, value: activeWorkers.filter((worker) => worker.risk_level === name).length }))
  const pieColors = ['#2dd4a3', '#f6c350', '#fb8c45', '#f45454']

  const getActivityMeta = (type: string) => {
    switch (type) {
      case 'NEAR_MISS':
        return { label: t.overview.activityNearMiss, dotClass: 'danger' }
      case 'WARNING':
        return { label: t.overview.activityWarning, dotClass: 'warning' }
      case 'INVESTIGATION':
        return { label: t.overview.activityInvestigation, dotClass: 'success' }
      case 'VOICE':
        return { label: t.overview.activityVoice, dotClass: 'info' }
      case 'SAFE':
        return { label: t.overview.activitySafe, dotClass: 'success' }
      default:
        return { label: t.overview.activityDefault, dotClass: '' }
    }
  }

  const deviceOnlinePercent = summary.data.total_devices > 0
    ? Math.round((summary.data.connected_devices / summary.data.total_devices) * 100)
    : 0

  const formatActivityMessage = (rawMsg: string) => {
    if (language === 'id') return rawMsg

    // Check direct dictionary first
    if (t.overview.activityMessages[rawMsg]) {
      return t.overview.activityMessages[rawMsg]
    }

    let translated = rawMsg
    // "Uji sinyal buzzer dikirim ke helm pekerja W01"
    translated = translated.replace(
      /^Uji sinyal buzzer dikirim ke helm pekerja ([\w-]+)/i,
      'Buzzer test signal sent to worker $1 helmet'
    )
    // "Sinyal buzzer dikirim ke pekerja W01 · Reason"
    translated = translated.replace(
      /^Sinyal buzzer dikirim ke pekerja ([\w-]+)/i,
      'Buzzer signal dispatched to worker $1'
    )
    // "Andi Pratama (W01) mendekati Forklift Alpha · RSSI -39.0 dBm"
    translated = translated.replace(
      / mendekati /g,
      ' approached '
    )
    // "Instruksi suara ke ..."
    translated = translated.replace(
      /^Instruksi suara ke /i,
      'Voice instruction to '
    )
    // "Pekerja ditandai aman oleh ..."
    translated = translated.replace(
      /^Pekerja ditandai aman oleh (.*)/i,
      'Worker marked safe by $1'
    )

    return translated
  }

  return <div className="stack-xl wide-page overview-page">
    <div className="page-intro">
      <div>
        <p className="eyebrow">{t.overview.eyebrow}</p>
        <h2>{t.overview.welcome(firstName)}</h2>
        <span>{t.overview.subtitle}</span>
      </div>
      <div className="overview-health"><div><strong>{t.common.systemOperational}</strong><span>{t.common.lastSync}</span></div></div>
    </div>
    {critical.length > 0 && (
      <div className="critical-banner">
        <div className="critical-icon"><Siren size={24} /></div>
        <div>
          <strong>{t.overview.criticalActive(critical.length)}</strong>
          <span>{critical.map((worker) => t.overview.nearHazard(worker.name, worker.hazard_name)).join(' · ')}</span>
        </div>
        <a href="/live">{t.overview.openLive}</a>
      </div>
    )}
    <div className="kpi-grid">
      <KpiCard label={t.overview.kpiActiveWorkers} value={summary.data.active_workers} detail={t.overview.kpiActiveWorkersDetail(summary.data.total_workers)} icon={Users} />
      <KpiCard label={t.overview.kpiActiveHazards} value={summary.data.active_hazards} detail={t.overview.kpiActiveHazardsDetail} icon={RadioTower} tone="amber" />
      <KpiCard label={t.overview.kpiHighRisk} value={activeWorkers.filter((w) => w.risk_level === 'HIGH').length} detail={t.overview.kpiHighRiskDetail} icon={AlertTriangle} tone="orange" />
      <KpiCard label={t.overview.kpiCriticalRisk} value={critical.length} detail={t.overview.kpiCriticalRiskDetail} icon={Siren} tone="red" />
      <KpiCard label={t.overview.kpiNearMissToday} value={summary.data.near_misses_today} detail={t.overview.kpiNearMissTodayDetail} icon={Gauge} tone="violet" />
      <KpiCard label={t.overview.kpiAvgRisk} value={summary.data.average_risk_score} unit="/100" detail={t.overview.kpiAvgRiskDetail} icon={ShieldCheck} tone="green" />
      <KpiCard label={t.overview.kpiConnectedDevices} value={`${summary.data.connected_devices}/${summary.data.total_devices}`} detail={t.overview.kpiConnectedDevicesDetail(deviceOnlinePercent)} icon={Cpu} tone="blue" />
      <KpiCard label={t.overview.kpiWarningLatency} value={summary.data.average_warning_latency} unit="ms" detail={t.overview.kpiWarningLatencyDetail} icon={Timer} tone="green" />
    </div>
    <div className="overview-grid main-charts">
      <Panel title={t.overview.panelWorkerRisk} subtitle={t.overview.panelWorkerRiskSub} action={<a className="text-link" href="/live">{t.common.viewAll} →</a>}>
        <div className="worker-risk-list">
          {activeWorkers.length === 0 ? (
            <div className="empty-state-card" style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--muted)', fontSize: '16px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
              <Users size={32} style={{ color: 'var(--muted)', opacity: 0.5 }} />
              <span>{t.overview.panelWorkerRiskEmpty}</span>
              <small style={{ fontSize: '12px' }}>{t.overview.panelWorkerRiskEmptySub}</small>
            </div>
          ) : (
            [...activeWorkers].sort((a, b) => b.risk_score - a.risk_score).slice(0, 5).map((worker) => (
              <a href={`/workers/${worker.id}`} key={worker.id}>
                <div className="avatar small">{worker.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</div>
                <div className="worker-list-name">
                  <strong>{worker.name}</strong>
                  <span>{worker.id} · {worker.hazard_name}</span>
                </div>
                <div className="mini-track">
                  <i style={{ width: `${worker.risk_score}%` }} />
                </div>
                <b className={`score score-${worker.risk_level.toLowerCase()}`}>{worker.risk_score}</b>
                <RiskBadge level={worker.risk_level} />
              </a>
            ))
          )}
        </div>
      </Panel>
      <Panel title={t.overview.panelDistribution} subtitle={t.overview.panelDistributionSub} className="distribution-panel">
        {activeWorkers.length === 0 ? (
          <div className="distribution-empty">
            <AlertTriangle size={32} style={{ color: 'var(--muted)', opacity: 0.5 }} />
            <span>{t.common.noData}</span>
          </div>
        ) : (
          <div className="overview-distribution-wrap">
            <div className="donut-visual">
              <ResponsiveContainer width={240} height={240}>
                <PieChart>
                  <Pie
                    data={distribution}
                    dataKey="value"
                    cx="50%"
                    cy="50%"
                    innerRadius={72}
                    outerRadius={104}
                    paddingAngle={4}
                  >
                    {distribution.map((entry, index) => (
                      <Cell key={entry.name} fill={pieColors[index]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: '#ffffff',
                      border: '1px solid #ced9e9',
                      borderRadius: 8,
                      boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
                    }}
                    itemStyle={{ color: '#142236', fontSize: 12, fontWeight: 600 }}
                    labelStyle={{ color: '#7b8ea9', fontSize: 12, marginBottom: 4 }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="donut-center-badge">
                <strong>{activeWorkers.length}</strong>
                <span>{t.nav.workers.toUpperCase()}</span>
              </div>
            </div>
            <div className="overview-legend">
              {distribution.map((item, index) => {
                const pct = activeWorkers.length > 0 ? Math.round((item.value / activeWorkers.length) * 100) : 0
                return (
                  <div key={item.name} className="overview-legend-item">
                    <div className="legend-row-top">
                      <div className="legend-label">
                        <span className="legend-dot" style={{ background: pieColors[index] }} />
                        <span className="legend-title">{item.name}</span>
                      </div>
                      <div className="legend-stats">
                        <strong className="legend-qty">{item.value}</strong>
                        <span className="legend-pct">({pct}%)</span>
                      </div>
                    </div>
                    <div className="legend-bar-bg">
                      <div className="legend-bar-fill" style={{ width: `${pct}%`, background: pieColors[index] }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </Panel>
    </div>
    <div className="overview-grid charts-row">
      <Panel title={t.overview.panelTrend} subtitle={t.overview.panelTrendSub} className="trend-panel">
        <ResponsiveContainer width="100%" height="100%" minHeight={270}>
          <AreaChart data={history.data?.items ?? []} margin={{ top: 16, right: 32, left: 8, bottom: 4 }}>
            <defs>
              <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#4f9cf9" stopOpacity={.35}/>
                <stop offset="100%" stopColor="#4f9cf9" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#ced9e9" strokeDasharray="4 4" vertical={false}/>
            <XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} stroke="#7b8ea9" fontSize={12}/>
            <YAxis stroke="#7b8ea9" fontSize={12} width={40}/>
            <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #ced9e9', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }} itemStyle={{ color: '#142236', fontSize: 12, fontWeight: 600 }} labelStyle={{ color: '#7b8ea9', fontSize: 12, marginBottom: 4 }}/>
            <Area dataKey="average_risk" name={t.overview.chartAvgRisk} stroke="#4f9cf9" fill="url(#riskFill)" strokeWidth={2}/>
          </AreaChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title={t.overview.chartNearMiss} subtitle={t.overview.panelTrendSub} className="trend-panel">
        <ResponsiveContainer width="100%" height="100%" minHeight={270}>
          <BarChart data={history.data?.items ?? []} margin={{ top: 16, right: 32, left: 8, bottom: 4 }}>
            <CartesianGrid stroke="#ced9e9" strokeDasharray="4 4" vertical={false}/>
            <XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} stroke="#7b8ea9" fontSize={12}/>
            <YAxis stroke="#7b8ea9" fontSize={12} width={40}/>
            <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #ced9e9', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }} itemStyle={{ color: '#142236', fontSize: 12, fontWeight: 600 }} labelStyle={{ color: '#7b8ea9', fontSize: 12, marginBottom: 4 }}/>
            <Bar dataKey="near_misses" name={t.overview.chartNearMiss} fill="#f6c350" radius={[4, 4, 0, 0]}/>
          </BarChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title={t.overview.panelActivity} subtitle={t.overview.panelActivitySub} action={<a className="text-link" href="/near-misses">{t.common.viewAll} →</a>}>
        <div className="activity-list">
          {(activities.data?.items ?? []).length === 0 ? (
            <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--muted)', fontSize: '13px' }}>
              {t.overview.activityEmpty}
            </div>
          ) : (
            activities.data?.items.slice(0, 4).map((item) => {
              const meta = getActivityMeta(item.type)
              return (
                <div key={item.id} className="activity-item">
                  <i className={`activity-dot ${meta.dotClass}`} />
                  <div className="activity-content">
                    <div className="activity-header">
                      <strong className="activity-title">{meta.label}</strong>
                    </div>
                    <span className="activity-message">{formatActivityMessage(item.message)}</span>
                  </div>
                  <time className="activity-time">{formatDate(item.timestamp)}</time>
                </div>
              )
            })
          )}
        </div>
      </Panel>
    </div>
  </div>
}
