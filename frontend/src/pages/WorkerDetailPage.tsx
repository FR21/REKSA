import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, ArrowLeft, BellRing, CheckCircle2, Cpu, HardHat, Radio, ShieldAlert, Thermometer, Wifi, Wind } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ErrorState, LoadingState } from '../components/common/States'
import { Panel } from '../components/common/Panel'
import { RiskBadge } from '../components/common/RiskBadge'
import { AIAdvisoryPanel } from '../components/workers/AIAdvisoryPanel'
import { Pagination } from '../components/common/Pagination'
import { formatDate } from '../lib/utils'
import { useProfile } from '../hooks/useProfile'
import { useTranslation } from '../i18n'
import { api } from '../services/api'
import type { NearMiss, Worker } from '../types'

interface WorkerDetail extends Worker {
  risk_factors: { factor: string; value: number }[]
  near_misses: NearMiss[]
}

export default function WorkerDetailPage() {
  const { workerId = '' } = useParams()
  const queryClient = useQueryClient()
  const { profile } = useProfile()
  const { t, language } = useTranslation()
  const [testSuccess, setTestSuccess] = useState('')
  const [nearMissPage, setNearMissPage] = useState(1)
  const nearMissPageSize = 5

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

  const testHelmetMutation = useMutation({
    mutationFn: () =>
      api('/warnings/test', {
        method: 'POST',
        body: JSON.stringify({
          worker_id: workerId,
          level: 'CRITICAL',
          reason: 'Uji Peringatan Helm oleh Supervisor',
          vibration: true,
          buzzer: true,
          duration_ms: 3000,
          confirmed: true,
        }),
      }),
    onSuccess: () => {
      setTestSuccess(t.workerDetail.testBuzzerSuccess)
      setTimeout(() => setTestSuccess(''), 4000)
    },
    onError: () => {
      alert(t.workerDetail.testBuzzerFailed)
    },
  })

  const acknowledgeMutation = useMutation({
    mutationFn: (eventId: string) =>
      api<NearMiss>(`/near-misses/${eventId}/acknowledge`, {
        method: 'PATCH',
        body: JSON.stringify({
          supervisor_name: `${profile.name} (${profile.role})`,
          note: language === 'en'
            ? 'Incident verified directly on worker profile.'
            : 'Insiden telah diverifikasi langsung pada profil pekerja.',
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['worker', workerId] })
      void queryClient.invalidateQueries({ queryKey: ['near-misses'] })
      void queryClient.invalidateQueries({ queryKey: ['summary'] })
      void queryClient.invalidateQueries({ queryKey: ['activity'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard-live'] })
    },
  })

  if (worker.isLoading) return <LoadingState />
  if (worker.isError || !worker.data) return <ErrorState retry={() => void worker.refetch()} />
  const data = worker.data

  const totalNearMisses = data.near_misses.length
  const ackCount = data.near_misses.filter((e) => e.acknowledged).length
  const pendingCount = totalNearMisses - ackCount

  return (
    <div className="stack-lg wide-page worker-detail-page">
      <Link className="back-link" to="/workers">
        <ArrowLeft size={16} />
        {t.workerDetail.back}
      </Link>

      <div className="worker-hero">
        <div className="avatar large">
          {data.name
            .split(' ')
            .map((part) => part[0])
            .slice(0, 2)
            .join('')}
        </div>
        <div className="worker-hero-copy">
          <span>
            {data.id} · {data.role}
          </span>
          <h2>{data.name}</h2>
          <p>
            {data.area} · {data.online ? t.workerDetail.shiftActive(formatDate(data.last_update, language)) : t.workerDetail.deviceOffline}
          </p>
          {testSuccess && (
            <div style={{ color: '#059669', fontSize: '12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              <CheckCircle2 size={16} /> {testSuccess}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {data.online && (
            <button
              className="button secondary"
              style={{ padding: '8px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}
              disabled={testHelmetMutation.isPending}
              onClick={() => testHelmetMutation.mutate()}
            >
              <BellRing size={16} />
              {testHelmetMutation.isPending ? t.workerDetail.testBuzzerSending : t.workerDetail.testBuzzer}
            </button>
          )}
          <div className="hero-risk">
            <span>{t.workerDetail.currentRiskScore}</span>
            <strong>{data.online ? data.risk_score : '-'}</strong>
            {data.online ? <RiskBadge level={data.risk_level} /> : <span style={{ fontSize: '12px', color: 'var(--muted)', fontWeight: 600 }}>-</span>}
          </div>
        </div>
      </div>

      <div className="status-strip" style={!data.online ? { opacity: 0.5 } : {}}>
        <div>
          <HardHat />
          <span>
            {t.workerDetail.smartHelmet}<b>{data.online ? t.common.online : t.common.offline}</b>
          </span>
        </div>
        <div>
          <Radio />
          <span>
            {t.workerDetail.nearestHazard}<b>{data.online ? data.hazard_name : '-'}</b>
          </span>
        </div>
        <div>
          <Thermometer />
          <span>
            {t.workerDetail.environment}<b>{data.online ? `${data.temperature}°C · ${data.humidity}%` : '-'}</b>
          </span>
        </div>
        <div>
          <Wind />
          <span>
            {t.workerDetail.airQuality}<b>{data.online ? data.air_quality_level : '-'}</b>
          </span>
        </div>
        <div>
          <Activity />
          <span>
            {t.workerDetail.impact}
            <b>
              {data.online
                ? `${data.impact_g.toFixed(1)}g · ${
                    data.fall_detected
                      ? t.workerDetail.impactFall
                      : data.impact
                      ? t.workerDetail.impactHit
                      : t.workerDetail.impactNormal
                  }`
                : '-'}
            </b>
          </span>
        </div>
        <div>
          <Wifi />
          <span>
            {t.workerDetail.signalRssi}<b>{data.online ? `${data.rssi} dBm` : '-'}</b>
          </span>
        </div>
      </div>

      <div className="detail-grid">
        <AIAdvisoryPanel advisory={data.ai_advisory} online={data.online} />

        <Panel title={t.workerDetail.actionTitle} subtitle={t.workerDetail.actionSubtitle} className="action-panel">
          <div className={`recommendation risk-bg-${data.risk_level.toLowerCase()}`}>
            <ShieldAlert size={32} />
            <div>
              <strong>
                {data.risk_level === 'CRITICAL'
                  ? t.workerDetail.actionCritical
                  : data.risk_level === 'HIGH'
                  ? t.workerDetail.actionHigh
                  : data.risk_level === 'MODERATE'
                  ? t.workerDetail.actionModerate
                  : t.workerDetail.actionSafe}
              </strong>
              <p>{t.workerDetail.actionRecommendations[data.recommended_action] ?? data.recommended_action}</p>
            </div>
          </div>
          <div className="source-line">
            <span>{t.workerDetail.dataSource}</span>
            <b>{data.calculation_source.replaceAll('_', ' ')}</b>
          </div>
        </Panel>

        <Panel title={t.workerDetail.auditTitle} subtitle={t.workerDetail.auditSubtitle}>
          <div
            className="distribution-wrap"
            style={{ height: '240px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', alignItems: 'stretch', width: '100%' }}
          >
            {totalNearMisses === 0 ? (
              <div
                className="empty-distribution"
                style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: '16px', flexDirection: 'column', gap: '8px' }}
              >
                <Cpu size={32} style={{ color: 'var(--muted)', opacity: 0.5 }} />
                <span>{t.workerDetail.auditEmpty}</span>
              </div>
            ) : (
              <>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '16px', padding: '0 8px', width: '100%' }}>
                  {[
                    {
                      label: t.workerDetail.auditVerified,
                      note: t.workerDetail.auditVerifiedSub,
                      count: ackCount,
                      color: '#16a34a',
                      background: '#f0fdf4',
                      bar: '#2dd4a3',
                    },
                    {
                      label: t.workerDetail.auditPending,
                      note: t.workerDetail.auditPendingSub,
                      count: pendingCount,
                      color: '#d97706',
                      background: '#fffbeb',
                      bar: '#f6c350',
                    },
                    {
                      label: t.workerDetail.auditCritical,
                      note: t.workerDetail.auditCriticalSub,
                      count: data.near_misses.filter((event) => event.risk_score >= 80).length,
                      color: '#dc2626',
                      background: '#fef2f2',
                      bar: '#f45454',
                    },
                  ].map((item) => (
                    <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '16px', width: '100%' }}>
                      <div
                        style={{
                          width: '40px',
                          height: '40px',
                          background: item.background,
                          color: item.color,
                          borderRadius: '8px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '20px',
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        {item.count}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <strong style={{ fontSize: '12px', color: '#142236', whiteSpace: 'nowrap' }}>{item.label}</strong>
                          <span style={{ fontSize: '12px', color: '#7b8ea9', whiteSpace: 'nowrap', marginLeft: '8px' }}>{item.note}</span>
                        </div>
                        <div style={{ width: '100%', height: '8px', background: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                          <div
                            style={{
                              width: `${totalNearMisses > 0 ? (item.count / totalNearMisses) * 100 : 0}%`,
                              height: '100%',
                              background: item.bar,
                              borderRadius: '4px',
                              transition: 'width 0.5s ease',
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="source-line" style={{ marginTop: 0, width: '100%' }}>
                  <span>{t.workerDetail.dataSource}</span>
                  <b>{t.workerDetail.auditSource}</b>
                </div>
              </>
            )}
          </div>
        </Panel>

        <Panel title={t.workerDetail.riskFactorTitle} subtitle={t.workerDetail.riskFactorSubtitle}>
          <ResponsiveContainer width="100%" height={245}>
            <BarChart
              data={data.risk_factors.map((item) => ({
                ...item,
                displayName: t.workerDetail.factorLabels[item.factor] ?? item.factor,
              }))}
              layout="vertical"
              margin={{ top: 8, right: 24, left: 16, bottom: 8 }}
            >
              <CartesianGrid stroke="#ced9e9" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} stroke="#7b8ea9" fontSize={12} />
              <YAxis type="category" dataKey="displayName" width={140} stroke="#7b8ea9" fontSize={12} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #ced9e9', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}
                itemStyle={{ color: '#142236', fontSize: 12, fontWeight: 600 }}
                labelStyle={{ color: '#7b8ea9', fontSize: 12, marginBottom: 4 }}
              />
              <Bar dataKey="value" fill="#4f9cf9" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel title={t.workerDetail.riskHistoryTitle} subtitle={t.workerDetail.riskHistorySubtitle}>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={history.data?.items ?? []}>
            <defs>
              <linearGradient id="workerRisk" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f6c350" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#f6c350" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#ced9e9" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tickFormatter={(value: string) => value.slice(5)} stroke="#7b8ea9" fontSize={12} />
            <YAxis stroke="#7b8ea9" fontSize={12} width={36} />
            <Tooltip
              contentStyle={{ background: '#ffffff', border: '1px solid #ced9e9', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}
              itemStyle={{ color: '#142236', fontSize: 12, fontWeight: 600 }}
              labelStyle={{ color: '#7b8ea9', fontSize: 12, marginBottom: 4 }}
            />
            <Area dataKey="score" stroke="#f6c350" fill="url(#workerRisk)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title={t.workerDetail.nearMissHistoryTitle} subtitle={t.workerDetail.nearMissHistorySubtitle(data.near_misses.length)}>
        {data.near_misses.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: 'var(--muted)', fontSize: '16px' }}>
            {t.workerDetail.nearMissEmpty}
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t.workerDetail.colTimestamp}</th>
                    <th>{t.workerDetail.colHazard}</th>
                    <th>{t.workerDetail.colRssi}</th>
                    <th>{t.workerDetail.colDuration}</th>
                    <th>{t.workerDetail.colRisk}</th>
                    <th>{t.workerDetail.colDangerLevel}</th>
                    <th>{t.workerDetail.colStatus}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.near_misses
                    .slice((nearMissPage - 1) * nearMissPageSize, nearMissPage * nearMissPageSize)
                    .map((event) => (
                    <tr key={event.id}>
                      <td>{formatDate(event.timestamp, language)}</td>
                      <td>
                        <strong>{event.hazard_name}</strong>
                        <small>{event.hazard_type}</small>
                      </td>
                      <td>{event.rssi} dBm</td>
                      <td>{event.duration.toFixed(1)} {language === 'en' ? 's' : 'dtk'}</td>
                      <td>
                        <b>{event.risk_score}</b>
                      </td>
                      <td>
                        <span
                          className={`ai-badge ${event.risk_score >= 80 ? 'high' : event.risk_score >= 50 ? 'medium' : 'low'}`}
                          style={{
                            fontSize: '12px',
                            padding: '4px 8px',
                            borderRadius: '4px',
                            fontWeight: 600,
                            background: event.risk_score >= 80 ? '#fef2f2' : event.risk_score >= 50 ? '#fffbeb' : '#f0fdf4',
                            color: event.risk_score >= 80 ? '#dc2626' : event.risk_score >= 50 ? '#d97706' : '#16a34a',
                          }}
                        >
                          {event.risk_score >= 80 ? 'HIGH' : event.risk_score >= 50 ? 'MEDIUM' : 'LOW'}
                        </span>
                      </td>
                      <td>
                        {event.acknowledged ? (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              color: '#059669',
                              fontWeight: 600,
                              fontSize: '12px',
                            }}
                          >
                            <CheckCircle2 size={16} /> {t.workerDetail.verifiedK3}
                          </span>
                        ) : (
                          <button
                            className="button primary"
                            style={{ padding: '4px 8px', fontSize: '12px' }}
                            disabled={acknowledgeMutation.isPending}
                            onClick={() => acknowledgeMutation.mutate(event.id)}
                          >
                            {t.workerDetail.btnAcknowledge}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              currentPage={nearMissPage}
              totalPages={Math.ceil(data.near_misses.length / nearMissPageSize) || 1}
              totalItems={data.near_misses.length}
              pageSize={nearMissPageSize}
              onPageChange={setNearMissPage}
              itemName={t.workerDetail.itemUnit}
            />
          </>
        )}
      </Panel>
    </div>
  )
}
