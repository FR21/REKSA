import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BellRing, Grid2X2, List, Search, SlidersHorizontal, Volume2 } from 'lucide-react'
import type { Worker } from '../types'
import { api } from '../services/api'
import { useLiveStore } from '../stores/liveStore'
import { WorkerCard } from '../components/workers/WorkerCard'
import { LoadingState, ErrorState, EmptyState } from '../components/common/States'
import { RiskBadge } from '../components/common/RiskBadge'
import { filterWorkers } from '../utils/filterWorkers'

export default function LiveMonitoringPage() {
  const [search, setSearch] = useState('')
  const [risk, setRisk] = useState('ALL')
  const [device, setDevice] = useState('ALL')
  const [view, setView] = useState<'grid' | 'table'>('grid')
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['workers'],
    queryFn: () => api<{ items: Worker[] }>('/workers'),
    refetchInterval: 2_000,
    refetchIntervalInBackground: true,
  })
  const workers = useLiveStore((state) => state.workers)
  const setWorkers = useLiveStore((state) => state.setWorkers)
  const updateWorker = useLiveStore((state) => state.updateWorker)
  useEffect(() => { if (query.data?.items) setWorkers(query.data.items) }, [query.data, setWorkers])
  const markSafe = useMutation({
    mutationFn: (workerId: string) => api<Worker>(`/workers/${workerId}/mark-safe`, { method: 'POST' }),
    onSuccess: (worker) => {
      updateWorker(worker)
      void queryClient.invalidateQueries()
    }
  })
  const testHelmet = useMutation({
    mutationFn: (workerId: string) => api('/warnings/test', { method: 'POST', body: JSON.stringify({ worker_id: workerId, level: 'CRITICAL', reason: 'Uji peringatan helm IoT oleh supervisor', vibration: true, buzzer: true, duration_ms: 3000, confirmed: true }) }),
    onSuccess: () => void queryClient.invalidateQueries()
  })
  const filtered = useMemo(() => filterWorkers(workers.length ? workers : query.data?.items ?? [], search, risk, device), [workers, query.data, search, risk, device])
  if (query.isLoading) return <LoadingState />
  if (query.isError) return <ErrorState retry={() => void query.refetch()} />
  const critical = filtered.filter((worker) => worker.risk_level === 'CRITICAL')
  return <div className="stack-lg wide-page live-monitoring-page">
    {critical.length > 0 && <div className="critical-banner"><div className="critical-icon"><Volume2 size={22}/></div><div><strong>CRITICAL SAFETY ALERT · {critical.length} WORKER</strong><span>{critical.map((w) => `${w.name} · ${w.hazard_name} · ${w.rssi} dBm`).join(' | ')}</span></div><button className="button danger" disabled={markSafe.isPending} onClick={() => markSafe.mutate(critical[0].id)}>Tandai Aman</button><button className="button secondary" disabled={testHelmet.isPending} onClick={() => testHelmet.mutate(critical[0].id)}><BellRing size={16}/> Test Helm</button></div>}
    <div className="toolbar"><div className="search-box"><Search size={17}/><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Cari nama atau ID pekerja..."/></div><div className="filter-control"><SlidersHorizontal size={16}/><select value={risk} onChange={(event) => setRisk(event.target.value)}><option value="ALL">Semua Risiko</option><option value="SAFE">Aman</option><option value="MODERATE">Moderat</option><option value="HIGH">Tinggi</option><option value="CRITICAL">Kritis</option></select></div><select className="select-control" value={device} onChange={(event) => setDevice(event.target.value)}><option value="ALL">Semua Perangkat</option><option value="ONLINE">Online</option><option value="OFFLINE">Offline</option></select><div className="view-toggle"><button className={view === 'grid' ? 'active' : ''} onClick={() => setView('grid')}><Grid2X2 size={17}/></button><button className={view === 'table' ? 'active' : ''} onClick={() => setView('table')}><List size={17}/></button></div></div>
    <div className="monitor-summary"><span><i className="status-dot online"/> {filtered.filter((w) => w.online).length} online</span><span>{filtered.length} pekerja ditampilkan</span><span>Urutan: Risiko tertinggi</span></div>
    {filtered.length === 0 ? <EmptyState label="Tidak ada pekerja yang cocok dengan filter."/> : view === 'grid' ? <div className="worker-card-grid">{filtered.map((worker) => <WorkerCard key={worker.id} worker={worker} onMarkSafe={worker.risk_level === 'CRITICAL' ? () => markSafe.mutate(worker.id) : undefined}/>)}</div> : <div className="table-wrap"><table><thead><tr><th>Worker</th><th>Risk</th><th>Bahaya terdekat</th><th>RSSI</th><th>Proximity</th><th>Exposure</th><th>Environment</th><th>Device</th></tr></thead><tbody>{filtered.map((worker) => <tr key={worker.id}><td><a href={`/workers/${worker.id}`}><strong>{worker.name}</strong><small>{worker.id} · {worker.area}</small></a></td><td><b className={`score score-${worker.risk_level.toLowerCase()}`}>{worker.risk_score}</b> <RiskBadge level={worker.risk_level}/></td><td><strong>{worker.hazard_name}</strong><small>{worker.hazard_status}</small></td><td className="mono">{worker.rssi} dBm</td><td><RiskBadge level={worker.proximity}/></td><td>{worker.exposure_seconds} dtk</td><td>{worker.temperature}°C · {worker.humidity}%</td><td><span className={`online-label ${!worker.online ? 'offline' : ''}`}><i/> {worker.online ? 'Online' : 'Offline'}</span></td></tr>)}</tbody></table></div>}
  </div>
}
