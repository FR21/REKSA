import { useState, useMemo, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  Filter,
  Search,
  ShieldAlert,
  UserCheck,
  FileCheck2,
  X,
} from 'lucide-react'
import { api, getErrorMessage } from '../services/api'
import { LoadingState, ErrorState, EmptyState } from '../components/common/States'
import { Panel } from '../components/common/Panel'
import { KpiCard } from '../components/dashboard/KpiCard'
import { RiskBadge } from '../components/common/RiskBadge'
import { Pagination } from '../components/common/Pagination'
import { formatDate } from '../lib/utils'
import { useProfile } from '../hooks/useProfile'
import { useTranslation } from '../i18n'
import type { NearMiss } from '../types'

export default function NearMissesPage() {
  const queryClient = useQueryClient()
  const { profile } = useProfile()
  const { t, language } = useTranslation()
  const [search, setSearch] = useState('')
  const [riskFilter, setRiskFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [selectedEvent, setSelectedEvent] = useState<NearMiss | null>(null)
  const [supervisorName, setSupervisorName] = useState(`${profile.name} (${profile.role})`)
  const [investigationNote, setInvestigationNote] = useState('')
  const [toastMsg, setToastMsg] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 6

  useEffect(() => {
    setSupervisorName(`${profile.name} (${profile.role})`)
  }, [profile.name, profile.role])

  const nearMissesQuery = useQuery({
    queryKey: ['near-misses', search, riskFilter, statusFilter],
    queryFn: () => {
      const params = new URLSearchParams()
      if (search) params.append('search', search)
      if (riskFilter !== 'ALL') params.append('risk_level', riskFilter)
      if (statusFilter === 'ACKNOWLEDGED') params.append('acknowledged', 'true')
      if (statusFilter === 'PENDING') params.append('acknowledged', 'false')
      params.append('page_size', '50')
      return api<{ items: NearMiss[]; total: number }>(`/near-misses?${params.toString()}`)
    },
    refetchInterval: 5_000,
  })

  const acknowledgeMutation = useMutation({
    mutationFn: ({ id, name, note }: { id: string; name: string; note: string }) =>
      api<NearMiss>(`/near-misses/${id}/acknowledge`, {
        method: 'PATCH',
        body: JSON.stringify({
          supervisor_name: name,
          note: note || (language === 'en'
            ? 'Incident has been verified and safety preventive measures applied.'
            : 'Insiden telah diverifikasi dan tindakan pencegahan K3 diterapkan.'),
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries()
      setSelectedEvent(null)
      setInvestigationNote('')
      setToastMsg(t.nearMisses.toastSuccess)
      setTimeout(() => setToastMsg(''), 4000)
    },
    onError: (err: unknown) => {
      alert(getErrorMessage(err, t.nearMisses.errorConfirm))
    },
  })

  const items = useMemo(() => nearMissesQuery.data?.items ?? [], [nearMissesQuery.data?.items])
  const total = nearMissesQuery.data?.total ?? 0
  const pendingCount = items.filter((item) => !item.acknowledged).length
  const acknowledgedCount = items.filter((item) => item.acknowledged).length
  const criticalCount = items.filter((item) => item.risk_level === 'CRITICAL').length

  const totalPages = Math.ceil(items.length / pageSize) || 1
  const paginatedItems = useMemo(() => {
    const start = (page - 1) * pageSize
    return items.slice(start, start + pageSize)
  }, [items, page, pageSize])

  useEffect(() => {
    if (page > totalPages) {
      setPage(1)
    }
  }, [totalPages, page])

  const handleOpenAcknowledge = (event: NearMiss) => {
    setSelectedEvent(event)
    setInvestigationNote(
      event.note || t.nearMisses.defaultNote(event.hazard_name, event.hazard_type, event.worker_name)
    )
  }

  const handleSubmitAcknowledge = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedEvent) return
    acknowledgeMutation.mutate({
      id: selectedEvent.id,
      name: supervisorName.trim() || (language === 'en' ? 'Safety Supervisor' : 'Supervisor K3'),
      note: investigationNote.trim(),
    })
  }

  if (nearMissesQuery.isLoading) return <LoadingState label={t.nearMisses.loading} />
  if (nearMissesQuery.isError) return <ErrorState retry={() => void nearMissesQuery.refetch()} />

  return (
    <div className="stack-lg wide-page near-misses-page">
      {toastMsg && (
        <div
          style={{
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            color: '#065f46',
            padding: '12px 16px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '12px',
            fontWeight: 600,
          }}
        >
          <CheckCircle2 size={16} /> {toastMsg}
        </div>
      )}

      <div className="kpi-grid">
        <KpiCard
          label={t.nearMisses.kpiTotal}
          value={total}
          detail={t.nearMisses.kpiTotalDetail}
          icon={ShieldAlert}
          tone="violet"
        />
        <KpiCard
          label={t.nearMisses.kpiPending}
          value={pendingCount}
          detail={t.nearMisses.kpiPendingDetail}
          icon={Clock}
          tone="orange"
        />
        <KpiCard
          label={t.nearMisses.kpiVerified}
          value={acknowledgedCount}
          detail={t.nearMisses.kpiVerifiedDetail}
          icon={CheckCircle2}
          tone="green"
        />
        <KpiCard
          label={t.nearMisses.kpiCritical}
          value={criticalCount}
          detail={t.nearMisses.kpiCriticalDetail}
          icon={AlertTriangle}
          tone="red"
        />
      </div>

      <div className="toolbar">
        <div className="search-box">
          <Search size={16} />
          <input
            type="text"
            placeholder={t.nearMisses.searchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="filter-control">
          <Filter size={16} />
          <select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
            <option value="ALL">{t.nearMisses.filterAllRisk}</option>
            <option value="CRITICAL">{t.nearMisses.filterCritical}</option>
            <option value="HIGH">{t.nearMisses.filterHigh}</option>
            <option value="MODERATE">{t.nearMisses.filterModerate}</option>
          </select>
        </div>

        <div className="filter-control">
          <FileCheck2 size={16} />
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="ALL">{t.nearMisses.filterAllStatus}</option>
            <option value="PENDING">{t.nearMisses.filterPending}</option>
            <option value="ACKNOWLEDGED">{t.nearMisses.filterAcknowledged}</option>
          </select>
        </div>

        <div className="toolbar-actions" style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
          <a
            href="/api/v1/near-misses/export"
            download
            className="button secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', textDecoration: 'none', whiteSpace: 'nowrap' }}
          >
            <Download size={16} />
            {t.common.exportCsv}
          </a>
        </div>
      </div>

      <Panel
        title={t.nearMisses.title}
        subtitle={t.nearMisses.desc}
      >
        {items.length === 0 ? (
          <EmptyState label={t.nearMisses.empty} />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t.nearMisses.colTime}</th>
                    <th>{t.nearMisses.colId}</th>
                    <th>{t.nearMisses.colWorker}</th>
                    <th>{t.nearMisses.colHazard}</th>
                    <th>{t.nearMisses.colSignalDuration}</th>
                    <th>{t.nearMisses.colRisk}</th>
                    <th>{t.nearMisses.colStatus}</th>
                    <th style={{ textAlign: 'right' }}>{t.nearMisses.colAction}</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedItems.map((event) => (
                    <tr key={event.id} className={!event.acknowledged ? 'highlight-row' : ''}>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <strong>{formatDate(event.timestamp, language)}</strong>
                          <small style={{ color: 'var(--muted)', fontSize: '12px' }}>
                            {t.nearMisses.sensorBleTrigger}
                          </small>
                        </div>
                      </td>
                      <td>
                        <span className="mono" style={{ fontWeight: 700, fontSize: '12px' }}>
                          {event.id}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div className="avatar small">
                            {event.worker_name.split(' ').map((p) => p[0]).slice(0, 2).join('')}
                          </div>
                          <div>
                            <a href={`/workers/${event.worker_id}`}>
                              <strong>{event.worker_name}</strong>
                            </a>
                            <small style={{ color: 'var(--muted)' }}>{event.worker_id}</small>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div>
                          <strong>{event.hazard_name}</strong>
                          <div style={{ display: 'flex', gap: '4px', marginTop: '2px' }}>
                            <span
                              style={{
                                fontSize: '12px',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontWeight: 700,
                                background: '#f1f5f9',
                                color: '#475569',
                              }}
                            >
                              {event.hazard_type}
                            </span>
                            <span
                              style={{
                                fontSize: '12px',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontWeight: 700,
                                background: event.hazard_status === 'MOVING' ? '#fef2f2' : '#f0fdf4',
                                color: event.hazard_status === 'MOVING' ? '#dc2626' : '#16a34a',
                              }}
                            >
                              {event.hazard_status}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div style={{ fontSize: '12px' }}>
                          <span className="mono">{event.rssi} dBm</span>
                          <div style={{ color: 'var(--muted)', fontSize: '12px' }}>
                            {t.nearMisses.durationSec(event.duration.toFixed(1))}
                          </div>
                        </div>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <b className={`score score-${event.risk_level.toLowerCase()}`}>
                            {event.risk_score}
                          </b>
                          <RiskBadge level={event.risk_level} />
                        </div>
                      </td>
                      <td>
                        {event.acknowledged ? (
                          <div>
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontSize: '12px',
                                fontWeight: 700,
                                color: '#059669',
                                background: '#ecfdf5',
                                padding: '4px 8px',
                                borderRadius: '8px',
                              }}
                            >
                              <CheckCircle2 size={16} /> {t.nearMisses.statusVerified}
                            </span>
                            {event.note && (
                              <p
                                style={{
                                  margin: '4px 0 0',
                                  fontSize: '12px',
                                  color: 'var(--muted)',
                                  maxWidth: '240px',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                }}
                                title={event.note}
                              >
                                "{event.note}"
                              </p>
                            )}
                          </div>
                        ) : (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '12px',
                              fontWeight: 700,
                              color: '#d97706',
                              background: '#fffbeb',
                              padding: '4px 8px',
                              borderRadius: '8px',
                            }}
                          >
                            <Clock size={16} /> {t.nearMisses.statusPending}
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          className={`button ${event.acknowledged ? 'secondary' : 'primary'}`}
                          style={{ padding: '4px 12px', fontSize: '12px' }}
                          onClick={() => handleOpenAcknowledge(event)}
                        >
                          {event.acknowledged ? t.nearMisses.btnChangeNote : t.nearMisses.btnTakeAction}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              totalItems={items.length}
              pageSize={pageSize}
              onPageChange={setPage}
              itemName={t.nearMisses.itemUnit}
            />
          </>
        )}
      </Panel>

      {/* MODAL INVESTIGASI & ACKNOWLEDGE */}
      {selectedEvent && (
        <div
          className="modal-overlay"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            display: 'grid',
            placeItems: 'center',
            zIndex: 9999,
            padding: '20px',
          }}
        >
          <div
            className="modal-card"
            style={{
              background: '#ffffff',
              borderRadius: '12px',
              maxWidth: '540px',
              width: '100%',
              boxShadow: '0 20px 24px -4px rgba(0, 0, 0, 0.2)',
              overflow: 'hidden',
              border: '1px solid #cbd5e1',
            }}
          >
            <div
              style={{
                padding: '16px 20px',
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: '#f8fafc',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldAlert size={20} style={{ color: '#0f78f6' }} />
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>
                  {t.nearMisses.modalTitle}
                </h3>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmitAcknowledge} style={{ padding: '20px' }}>
              <div
                style={{
                  background: '#f1f5f9',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  marginBottom: '16px',
                  fontSize: '12px',
                }}
              >
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <div>
                    <span style={{ color: 'var(--muted)', fontSize: '12px' }}>{t.nearMisses.modalIncidentId}:</span>
                    <div className="mono" style={{ fontWeight: 700 }}>
                      {selectedEvent.id}
                    </div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--muted)', fontSize: '12px' }}>{t.nearMisses.modalTime}:</span>
                    <div style={{ fontWeight: 600 }}>{formatDate(selectedEvent.timestamp, language)}</div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--muted)', fontSize: '12px' }}>{t.nearMisses.modalWorker}:</span>
                    <div style={{ fontWeight: 700 }}>{selectedEvent.worker_name}</div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--muted)', fontSize: '12px' }}>{t.nearMisses.modalHazard}:</span>
                    <div style={{ fontWeight: 700 }}>{selectedEvent.hazard_name}</div>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600 }}>{t.nearMisses.supervisorLabel}</span>
                  <input
                    type="text"
                    value={supervisorName}
                    onChange={(e) => setSupervisorName(e.target.value)}
                    required
                    style={{
                      height: '40px',
                      borderRadius: '8px',
                      border: '1px solid #cbd5e1',
                      padding: '0 12px',
                      fontSize: '12px',
                    }}
                  />
                </label>

                <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600 }}>
                    {t.nearMisses.noteLabel}
                  </span>
                  <textarea
                    rows={4}
                    value={investigationNote}
                    onChange={(e) => setInvestigationNote(e.target.value)}
                    placeholder={t.nearMisses.notePlaceholder}
                    required
                    style={{
                      borderRadius: '8px',
                      border: '1px solid #cbd5e1',
                      padding: '12px',
                      fontSize: '12px',
                      resize: 'vertical',
                      fontFamily: 'inherit',
                    }}
                  />
                </label>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: '12px',
                  marginTop: '20px',
                  borderTop: '1px solid #e2e8f0',
                  paddingTop: '16px',
                }}
              >
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setSelectedEvent(null)}
                >
                  {t.common.cancel}
                </button>
                <button
                  type="submit"
                  className="button primary"
                  disabled={acknowledgeMutation.isPending}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                >
                  <UserCheck size={16} />
                  {acknowledgeMutation.isPending ? t.nearMisses.btnSaving : t.nearMisses.btnSave}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
