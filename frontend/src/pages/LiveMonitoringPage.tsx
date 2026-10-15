import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BellRing, Grid2X2, HardHat, List, Search, SlidersHorizontal, Volume2 } from 'lucide-react'
import type { Worker } from '../types'
import { api } from '../services/api'
import { useLiveStore } from '../stores/liveStore'
import { WorkerCard } from '../components/workers/WorkerCard'
import { LoadingState, ErrorState, EmptyState } from '../components/common/States'
import { RiskBadge } from '../components/common/RiskBadge'
import { VoiceDispatcherPanel } from '../components/voice/VoiceDispatcherPanel'
import { Pagination } from '../components/common/Pagination'
import { filterWorkers } from '../utils/filterWorkers'
import { useTranslation } from '../i18n'

export default function LiveMonitoringPage() {
  const { t, language } = useTranslation()
  const [search, setSearch] = useState('')
  const [risk, setRisk] = useState('ALL')
  const [device, setDevice] = useState('ALL')
  const [view, setView] = useState<'grid' | 'table'>('grid')
  const [page, setPage] = useState(1)
  const pageSize = 6
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

  useEffect(() => {
    if (query.data?.items) setWorkers(query.data.items)
  }, [query.data, setWorkers])

  const markSafe = useMutation({
    mutationFn: (workerId: string) => api<Worker>(`/workers/${workerId}/mark-safe`, { method: 'POST' }),
    onSuccess: (worker) => {
      updateWorker(worker)
      void queryClient.invalidateQueries()
    },
  })

  const testHelmet = useMutation({
    mutationFn: (workerId: string) =>
      api('/warnings/test', {
        method: 'POST',
        body: JSON.stringify({
          worker_id: workerId,
          level: 'CRITICAL',
          reason: 'Uji peringatan helm IoT oleh supervisor',
          vibration: true,
          buzzer: true,
          duration_ms: 3000,
          confirmed: true,
        }),
      }),
    onSuccess: () => void queryClient.invalidateQueries(),
  })

  const filtered = useMemo(
    () => filterWorkers(workers.length ? workers : query.data?.items ?? [], search, risk, device),
    [workers, query.data, search, risk, device]
  )

  const totalPages = Math.ceil(filtered.length / pageSize) || 1
  const paginatedWorkers = useMemo(() => {
    const start = (page - 1) * pageSize
    return filtered.slice(start, start + pageSize)
  }, [filtered, page, pageSize])

  useEffect(() => {
    if (page > totalPages) {
      setPage(1)
    }
  }, [totalPages, page])

  if (query.isLoading) return <LoadingState label={t.common.loading} />
  if (query.isError) return <ErrorState retry={() => void query.refetch()} />

  const critical = filtered.filter((worker) => worker.risk_level === 'CRITICAL')

  return (
    <div className="stack-lg wide-page live-monitoring-page">
      {critical.length > 0 && (
        <div className="critical-banner">
          <div className="critical-icon">
            <Volume2 size={24} />
          </div>
          <div>
            <strong>{t.overview.criticalActive(critical.length)}</strong>
            <span>{critical.map((w) => `${w.name} · ${w.hazard_name} · ${w.rssi} dBm`).join(' | ')}</span>
          </div>
          <button className="button danger" disabled={markSafe.isPending} onClick={() => markSafe.mutate(critical[0].id)}>
            {t.live.cardMarkSafe}
          </button>
          <button className="button secondary" disabled={testHelmet.isPending} onClick={() => testHelmet.mutate(critical[0].id)}>
            <BellRing size={16} /> {t.live.cardBuzzerTest}
          </button>
        </div>
      )}

      <VoiceDispatcherPanel />

      <div className="toolbar">
        <div className="search-box">
          <Search size={16} />
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
            placeholder={t.live.searchPlaceholder}
          />
        </div>
        <div className="filter-control">
          <SlidersHorizontal size={16} />
          <select
            value={risk}
            onChange={(event) => {
              setRisk(event.target.value)
              setPage(1)
            }}
          >
            <option value="ALL">{t.live.filterAllRisk}</option>
            <option value="SAFE">{t.live.filterSafe}</option>
            <option value="MODERATE">{t.live.filterModerate}</option>
            <option value="HIGH">{t.live.filterHigh}</option>
            <option value="CRITICAL">{t.live.filterCritical}</option>
          </select>
        </div>
        <div className="filter-control">
          <HardHat size={16} />
          <select
            value={device}
            onChange={(event) => {
              setDevice(event.target.value)
              setPage(1)
            }}
          >
            <option value="ALL">{t.live.filterAllDevices}</option>
            <option value="ONLINE">{t.common.online}</option>
            <option value="OFFLINE">{t.common.offline}</option>
          </select>
        </div>
        <div className="view-toggle">
          <button className={view === 'grid' ? 'active' : ''} onClick={() => setView('grid')} title={language === 'id' ? 'Tampilan Kartu Grid' : 'Grid View'}>
            <Grid2X2 size={16} />
          </button>
          <button className={view === 'table' ? 'active' : ''} onClick={() => setView('table')} title={language === 'id' ? 'Tampilan Tabel Detail' : 'Table View'}>
            <List size={16} />
          </button>
        </div>
      </div>

      <div className="monitor-summary">
        <span>
          <i className="status-dot online" /> {filtered.filter((w) => w.online).length} {t.common.online}
        </span>
        <span>{t.live.showing(paginatedWorkers.length, filtered.length)}</span>
      </div>

      {filtered.length === 0 ? (
        <EmptyState label={t.live.empty} />
      ) : view === 'grid' ? (
        <>
          <div className="worker-card-grid">
            {paginatedWorkers.map((worker) => (
              <WorkerCard
                key={worker.id}
                worker={worker}
                onMarkSafe={worker.risk_level === 'CRITICAL' ? () => markSafe.mutate(worker.id) : undefined}
                onTestHelmet={worker.online ? () => testHelmet.mutate(worker.id) : undefined}
              />
            ))}
          </div>
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            totalItems={filtered.length}
            pageSize={pageSize}
            onPageChange={setPage}
            itemName={t.nav.workers.toLowerCase()}
          />
        </>
      ) : (
        <>
          <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t.nav.workers}</th>
                <th>{t.live.cardRiskScore}</th>
                <th>{t.live.cardHazardNearby}</th>
                <th>RSSI</th>
                <th>Proximity</th>
                <th>{language === 'en' ? 'Exposure' : 'Paparan'}</th>
                <th>{t.live.cardAir}</th>
                <th>{language === 'en' ? 'Device' : 'Perangkat'}</th>
                <th style={{ textAlign: 'right' }}>{t.common.action}</th>
              </tr>
            </thead>
            <tbody>
              {paginatedWorkers.map((worker) => (
                <tr key={worker.id} className={!worker.online ? 'offline-row' : ''} style={!worker.online ? { opacity: 0.5 } : {}}>
                  <td>
                    <a href={`/workers/${worker.id}`}>
                      <strong>{worker.name}</strong>
                      <small>
                        {worker.id} · {worker.area}
                      </small>
                    </a>
                  </td>
                  <td>
                    {worker.online ? (
                      <>
                        <b className={`score score-${worker.risk_level.toLowerCase()}`}>{worker.risk_score}</b>{' '}
                        <RiskBadge level={worker.risk_level} />
                      </>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td>
                    {worker.online ? (
                      <>
                        <strong>{worker.hazard_name}</strong>
                        <small>
                          {worker.hazard_category ? `[${worker.hazard_category}] ` : ''}
                          {worker.hazard_status}
                        </small>
                      </>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td className="mono">{worker.online ? `${worker.rssi} dBm` : '-'}</td>
                  <td>{worker.online ? <RiskBadge level={worker.proximity} /> : '-'}</td>
                  <td>{worker.online ? `${worker.exposure_seconds} ${language === 'en' ? 's' : 'dtk'}` : '-'}</td>
                  <td>{worker.online ? `${worker.temperature}°C · ${worker.humidity}%` : '-'}</td>
                  <td>
                    <span className={`online-label ${!worker.online ? 'offline' : ''}`}>
                      <i /> {worker.online ? t.common.online : t.common.offline}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    {worker.online && (
                      <button
                        className="button secondary"
                        style={{ padding: '4px 8px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                        disabled={testHelmet.isPending}
                        onClick={() => testHelmet.mutate(worker.id)}
                        title={t.live.cardBuzzerTest}
                      >
                        <BellRing size={12} /> {t.live.cardBuzzerTest}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination
          currentPage={page}
          totalPages={totalPages}
          totalItems={filtered.length}
          pageSize={pageSize}
          onPageChange={setPage}
          itemName={t.nav.workers.toLowerCase()}
        />
      </>
    )}
    </div>
  )
}
