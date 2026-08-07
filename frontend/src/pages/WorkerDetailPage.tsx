import { useQuery } from '@tanstack/react-query'
import { Activity, ArrowLeft, HardHat, Radio, ShieldAlert, Thermometer, Wifi, Wind } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../services/api'
import type { NearMiss, Worker } from '../types'
import { ErrorState, LoadingState } from '../components/common/States'
import { Panel } from '../components/common/Panel'
import { RiskBadge } from '../components/common/RiskBadge'
import { formatDate } from '../lib/utils'

interface WorkerDetail extends Worker { risk_factors: { factor: string; value: number }[]; near_misses: NearMiss[] }

export default function WorkerDetailPage() {
  const { workerId = '' } = useParams()
  const worker = useQuery({
    queryKey: ['worker', workerId],
    queryFn: () => api<WorkerDetail>(`/workers/${workerId}`),
    refetchInterval: 2_000,
    refetchIntervalInBackground: true,
  })
  const history = useQuery({
    queryKey: ['worker-history', workerId],
    queryFn: () => api<{ items: { date: string; score: number }[] }>(`/workers/${workerId}/risk-history`),
    refetchInterval: 10_000,
  })
  if (worker.isLoading) return <LoadingState />
  if (worker.isError || !worker.data) return <ErrorState retry={() => void worker.refetch()} />
  const data = worker.data
  return <div className="stack-lg wide-page worker-detail-page"><Link className="back-link" to="/workers"><ArrowLeft size={16}/> Kembali ke daftar pekerja</Link><div className="worker-hero"><div className="avatar large">{data.name.split(' ').map((p) => p[0]).slice(0, 2).join('')}</div><div className="worker-hero-copy"><span>{data.id} · {data.role}</span><h2>{data.name}</h2><p>{data.area} · Shift Pagi · 7 jam 12 menit aktif</p></div><div className="hero-risk"><span>Current Risk Score</span><strong>{data.risk_score}</strong><RiskBadge level={data.risk_level}/></div></div><div className="status-strip"><div><HardHat/><span>Smart Helmet<b>{data.online ? 'Online' : 'Offline'}</b></span></div><div><Radio/><span>Nearest Hazard<b>{data.hazard_name}</b></span></div><div><Thermometer/><span>Environment<b>{data.temperature}°C · {data.humidity}%</b></span></div><div><Wind/><span>Air Quality<b>{data.air_quality_level}</b></span></div><div><Activity/><span>Impact<b>{data.impact_g.toFixed(1)}g · {data.fall_detected ? 'Fall' : data.impact ? 'Hit' : 'Normal'}</b></span></div><div><Wifi/><span>Signal RSSI<b>{data.rssi} dBm</b></span></div></div><div className="detail-grid"><Panel title="Recommended Supervisor Action" subtitle="Tindakan berdasarkan assessment terbaru" className="action-panel"><div className={`recommendation risk-bg-${data.risk_level.toLowerCase()}`}><ShieldAlert size={28}/><div><strong>{data.risk_level === 'CRITICAL' ? 'Tindakan segera diperlukan' : 'Rekomendasi sistem'}</strong><p>{data.recommended_action}</p></div></div><div className="source-line"><span>SUMBER DATA</span><b>{data.calculation_source.replaceAll('_', ' ')}</b></div></Panel><Panel title="Risk Factor Summary" subtitle="Kontribusi dominan pada skor saat ini"><ResponsiveContainer width="100%" height={245}><BarChart data={data.risk_factors} layout="vertical" margin={{ left: 20 }}><CartesianGrid stroke="#ced9e9" horizontal={false}/><XAxis type="number" domain={[0, 100]} stroke="#7b8ea9"/><YAxis type="category" dataKey="factor" width={110} stroke="#7b8ea9" fontSize={11}/><Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #ced9e9', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }} itemStyle={{ color: '#142236', fontSize: 13, fontWeight: 600 }} labelStyle={{ color: '#7b8ea9', fontSize: 11, marginBottom: 4 }}/><Bar dataKey="value" fill="#4f9cf9" radius={[0, 5, 5, 0]}/></BarChart></ResponsiveContainer></Panel></div><Panel title="Risk History" subtitle="Perubahan skor risiko selama 14 hari"><ResponsiveContainer width="100%" height={260}><AreaChart data={history.data?.items ?? []}><defs><linearGradient id="workerRisk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#f6c350" stopOpacity={.35}/><stop offset="1" stopColor="#f6c350" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#ced9e9" strokeDasharray="3 3" vertical={false}/><XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} stroke="#7b8ea9"/><YAxis stroke="#7b8ea9"/><Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #ced9e9', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }} itemStyle={{ color: '#142236', fontSize: 13, fontWeight: 600 }} labelStyle={{ color: '#7b8ea9', fontSize: 11, marginBottom: 4 }}/><Area dataKey="score" stroke="#f6c350" fill="url(#workerRisk)" strokeWidth={2}/></AreaChart></ResponsiveContainer></Panel><Panel title="Near-Miss History" subtitle={`${data.near_misses.length} kejadian terkait pekerja`}>{data.near_misses.length === 0 ? <div style={{ padding: '24px', textAlign: 'center', color: 'var(--muted)', fontSize: '14px' }}>Tidak ada riwayat Near-Miss untuk pekerja ini.</div> : <div className="table-wrap"><table><thead><tr><th>Timestamp</th><th>Hazard</th><th>RSSI</th><th>Duration</th><th>Risk</th><th>Status</th></tr></thead><tbody>{data.near_misses.map((event) => <tr key={event.id}><td>{formatDate(event.timestamp)}</td><td><strong>{event.hazard_name}</strong><small>{event.hazard_type}</small></td><td>{event.rssi} dBm</td><td>{event.duration.toFixed(1)} dtk</td><td><b>{event.risk_score}</b></td><td>{event.acknowledged ? 'Acknowledged' : 'Needs review'}</td></tr>)}</tbody></table></div>}</Panel></div>
}
