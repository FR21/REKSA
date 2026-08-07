import { Activity, Clock3, Radio, Thermometer, Wifi, WifiOff, Wind } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Worker } from '../../types'
import { RiskBadge } from '../common/RiskBadge'

export function WorkerCard({ worker, onMarkSafe }: { worker: Worker; onMarkSafe?: () => void }) {
  return <article className={`worker-card ${worker.risk_level === 'CRITICAL' ? 'critical-card' : ''}`}>
    <div className="worker-card-head"><div className="avatar">{worker.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</div><div><Link to={`/workers/${worker.id}`}>{worker.name}</Link><span>{worker.id} · {worker.area}</span></div><RiskBadge level={worker.risk_level} /></div>
    <div className="risk-score-row"><div><span>RISK SCORE</span><strong>{worker.risk_score}</strong><small>/100</small></div><div className="score-track"><i style={{ width: `${worker.risk_score}%` }} /></div></div>
    <div className="hazard-line"><Radio size={16} /><div><span>Bahaya terdekat</span><strong>{worker.hazard_name}</strong></div><b>{worker.rssi} dBm</b></div>
    <div className="worker-grid"><span><Clock3 size={14} /> Paparan <b>{worker.exposure_seconds} dtk</b></span><span><Thermometer size={14} /> Suhu <b>{worker.temperature}°C</b></span><span><Wind size={14} /> Udara <b>{worker.air_quality_level}</b></span><span><Activity size={14} /> Impact <b>{worker.impact_g.toFixed(1)}g</b></span><span>{worker.online ? <Wifi size={14} /> : <WifiOff size={14} />} Status <b>{worker.online ? 'Online' : 'Offline'}</b></span></div>
    {worker.risk_level === 'CRITICAL' && <div className="critical-actions"><span><i className="pulse-dot" /> TINDAKAN SEGERA DIPERLUKAN</span>{onMarkSafe && <button onClick={onMarkSafe}>Tandai Aman</button>}</div>}
  </article>
}
