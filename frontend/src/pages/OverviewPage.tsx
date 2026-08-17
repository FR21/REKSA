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

interface Summary { active_workers: number; total_workers: number; active_hazards: number; high_risk_workers: number; critical_risk_workers: number; near_misses_today: number; average_risk_score: number; connected_devices: number; total_devices: number; average_warning_latency: number }
interface LiveData { workers: Worker[]; critical_alerts: Worker[]; risk_distribution: Record<string, number>; hazards: Hazard[] }

export default function OverviewPage() {
  const summary = useQuery({ queryKey: ['summary'], queryFn: () => api<Summary>('/dashboard/summary'), refetchInterval: 10_000 })
  const live = useQuery({ queryKey: ['dashboard-live'], queryFn: () => api<LiveData>('/dashboard/live') })
  const history = useQuery({ queryKey: ['risk-trend', '7d'], queryFn: () => api<{ items: HistoryPoint[] }>('/analytics/risk-trend?period=7d') })
  const activities = useQuery({ queryKey: ['activity'], queryFn: () => api<{ items: { id: string; type: string; message: string; timestamp: string }[] }>('/dashboard/activity') })
  const workers = useLiveStore((state) => state.workers)
  const setWorkers = useLiveStore((state) => state.setWorkers)
  useEffect(() => { if (live.data?.workers && workers.length === 0) setWorkers(live.data.workers) }, [live.data, setWorkers, workers.length])

  if (summary.isLoading || live.isLoading) return <LoadingState label="Menyiapkan command center..." />
  if (summary.isError || live.isError || !summary.data || !live.data) return <ErrorState retry={() => { void summary.refetch(); void live.refetch() }} />
  const activeWorkers = (workers.length ? workers : live.data.workers).filter((worker) => worker.online)
  const critical = activeWorkers.filter((worker) => worker.risk_level === 'CRITICAL')
  const distribution = ['SAFE', 'MODERATE', 'HIGH', 'CRITICAL'].map((name) => ({ name, value: activeWorkers.filter((worker) => worker.risk_level === name).length }))
  const pieColors = ['#2dd4a3', '#f6c350', '#fb8c45', '#f45454']

  return <div className="stack-xl wide-page overview-page">
    <div className="page-intro"><div><p className="eyebrow">LIVE SAFETY OVERVIEW</p><h2>Selamat datang, Raka.</h2><span>Pantau kondisi keselamatan operasional secara real-time dari satu command center.</span></div><div className="overview-health"><div><strong>System Operational</strong><span>Terakhir sinkron · baru saja</span></div></div></div>
    {critical.length > 0 && <div className="critical-banner"><div className="critical-icon"><Siren size={24} /></div><div><strong>{critical.length} PERINGATAN KRITIS AKTIF</strong><span>{critical.map((worker) => `${worker.name} dekat ${worker.hazard_name}`).join(' · ')}</span></div><a href="/live">Buka Live Monitoring</a></div>}
    <div className="kpi-grid">
      <KpiCard label="ACTIVE WORKERS" value={summary.data.active_workers} detail={`dari ${summary.data.total_workers} pekerja terdaftar`} icon={Users} />
      <KpiCard label="ACTIVE HAZARDS" value={summary.data.active_hazards} detail="node bahaya beroperasi" icon={RadioTower} tone="amber" />
      <KpiCard label="HIGH RISK" value={activeWorkers.filter((w) => w.risk_level === 'HIGH').length} detail="memerlukan perhatian" icon={AlertTriangle} tone="orange" />
      <KpiCard label="CRITICAL RISK" value={critical.length} detail="tindakan segera" icon={Siren} tone="red" />
      <KpiCard label="NEAR MISS TODAY" value={summary.data.near_misses_today} detail="kejadian terdeteksi" icon={Gauge} tone="violet" />
      <KpiCard label="AVG. RISK SCORE" value={activeWorkers.length ? Math.round(activeWorkers.reduce((sum, w) => sum + w.risk_score, 0) / activeWorkers.length) : 0} unit="/100" detail="seluruh pekerja aktif" icon={ShieldCheck} tone="green" />
      <KpiCard label="CONNECTED DEVICES" value={`${summary.data.connected_devices}/${summary.data.total_devices}`} detail={summary.data.total_devices > 0 ? `${Math.round((summary.data.connected_devices / summary.data.total_devices) * 100)}% node online` : '0% node online'} icon={Cpu} tone="blue" />
      <KpiCard label="WARNING LATENCY" value={summary.data.average_warning_latency} unit="ms" detail="rata-rata pengiriman" icon={Timer} tone="green" />
    </div>
    <div className="overview-grid main-charts">
      <Panel title="Live Worker Risk" subtitle="Pekerja diurutkan berdasarkan skor risiko tertinggi" action={<a className="text-link" href="/live">Lihat semua →</a>}>
        <div className="worker-risk-list">
          {activeWorkers.length === 0 ? (
            <div className="empty-state-card" style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--muted)', fontSize: '14px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
              <Users size={32} style={{ color: 'var(--muted)', opacity: 0.5 }} />
              <span>Tidak ada data pekerja aktif terdeteksi.</span>
              <small style={{ fontSize: '12px' }}>Silakan daftarkan pekerja & hubungkan perangkat IoT di halaman pengaturan.</small>
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
      <Panel title="Risk Distribution" subtitle="Klasifikasi pekerja aktif saat ini">
        {activeWorkers.length === 0 ? (
          <div className="distribution-wrap empty-distribution" style={{ height: '225px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: '14px', flexDirection: 'column', gap: '8px' }}>
            <AlertTriangle size={32} style={{ color: 'var(--muted)', opacity: 0.5 }} />
            <span>Belum ada data distribusi risiko.</span>
          </div>
        ) : (
          <div className="distribution-wrap">
            <ResponsiveContainer width="58%" height={225}>
              <PieChart>
                <Pie data={distribution} dataKey="value" innerRadius={60} outerRadius={86} paddingAngle={3}>
                  {distribution.map((entry, index) => <Cell key={entry.name} fill={pieColors[index]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #ced9e9', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }} itemStyle={{ color: '#142236', fontSize: 13, fontWeight: 600 }} labelStyle={{ color: '#7b8ea9', fontSize: 11, marginBottom: 4 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="chart-legend">
              {distribution.map((item, index) => <div key={item.name}><span style={{ background: pieColors[index] }} /><b>{item.value}</b><small>{item.name}</small></div>)}
            </div>
            <div className="donut-center">
              <strong>{activeWorkers.length}</strong>
              <span>WORKERS</span>
            </div>
          </div>
        )}
      </Panel>
    </div>
    <div className="overview-grid charts-row">
      <Panel title="Risk Score Trend" subtitle="Rata-rata skor risiko · 7 hari terakhir" className="trend-panel"><ResponsiveContainer width="100%" height={240}><AreaChart data={history.data?.items ?? []} margin={{ top: 18, right: 32, left: 8, bottom: 4 }}><defs><linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#4f9cf9" stopOpacity={.35}/><stop offset="100%" stopColor="#4f9cf9" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#ced9e9" strokeDasharray="3 3" vertical={false}/><XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} stroke="#7b8ea9" fontSize={11}/><YAxis stroke="#7b8ea9" fontSize={11} width={42}/><Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #ced9e9', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }} itemStyle={{ color: '#142236', fontSize: 13, fontWeight: 600 }} labelStyle={{ color: '#7b8ea9', fontSize: 11, marginBottom: 4 }}/><Area dataKey="average_risk" stroke="#4f9cf9" fill="url(#riskFill)" strokeWidth={2}/></AreaChart></ResponsiveContainer></Panel>
      <Panel title="Near-Miss Trend" subtitle="Deteksi otomatis · 7 hari terakhir" className="trend-panel"><ResponsiveContainer width="100%" height={240}><BarChart data={history.data?.items ?? []} margin={{ top: 18, right: 32, left: 8, bottom: 4 }}><CartesianGrid stroke="#ced9e9" strokeDasharray="3 3" vertical={false}/><XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} stroke="#7b8ea9" fontSize={11}/><YAxis stroke="#7b8ea9" fontSize={11} width={42}/><Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #ced9e9', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }} itemStyle={{ color: '#142236', fontSize: 13, fontWeight: 600 }} labelStyle={{ color: '#7b8ea9', fontSize: 11, marginBottom: 4 }}/><Bar dataKey="near_misses" fill="#f6c350" radius={[4, 4, 0, 0]}/></BarChart></ResponsiveContainer></Panel>
      <Panel title="Recent System Activity" subtitle="Aktivitas terbaru dari seluruh node"><div className="activity-list" style={{ height: '240px', overflowY: 'auto', paddingRight: '8px' }}>{activities.data?.items.map((item) => <div key={item.id}><i className={item.type === 'NEAR_MISS' ? 'danger' : ''} /><div><strong>{item.type === 'NEAR_MISS' ? 'Near-miss terdeteksi' : 'Pembaruan perangkat'}</strong><span>{item.message}</span></div><time>{formatDate(item.timestamp)}</time></div>)}</div></Panel>
    </div>
  </div>
}
