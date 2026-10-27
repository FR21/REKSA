import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertOctagon,
  AlertTriangle,
  BellRing,
  CheckCircle2,
  Clock,
  History,
  MapPin,
  Mic,
  Pause,
  Play,
  Radio,
  ShieldAlert,
  Volume2,
} from 'lucide-react'
import { api, API_URL } from '../../services/api'
import { useLiveStore } from '../../stores/liveStore'
import { useTranslation } from '../../i18n'
import type { VoiceTransmission } from '../../types'
import { formatDate } from '../../lib/utils'

export function VoiceDispatcherPanel() {
  const queryClient = useQueryClient()
  const { t, language } = useTranslation()
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [feedbackMsg, setFeedbackMsg] = useState('')

  const transmissionsQuery = useQuery({
    queryKey: ['voice-transmissions'],
    queryFn: () =>
      api<{
        items: VoiceTransmission[]
        total: number
        latest: VoiceTransmission | null
        audio_available: boolean
      }>('/voice/transmissions'),
    refetchInterval: 5_000,
  })

  const liveLatest = useLiveStore((state) => state.latestTransmission)
  const allItems = transmissionsQuery.data?.items ?? []
  const unhandledItems = allItems.filter((item) => !item.acknowledged)
  const activeTransmission: VoiceTransmission | null =
    (liveLatest && !liveLatest.acknowledged ? liveLatest : null) ||
    unhandledItems[0] ||
    null

  const acknowledgeMutation = useMutation({
    mutationFn: (id: string) =>
      api<VoiceTransmission>(`/voice/transmissions/${id}/acknowledge`, {
        method: 'POST',
        body: JSON.stringify({
          supervisor_note:
            language === 'en'
              ? 'Verified in command center and followed up'
              : 'Diverifikasi langsung di command center dan ditindaklanjuti',
          action_taken: 'VERIFIED_IN_PERSON',
        }),
      }),
    onSuccess: (_updated, id) => {
      useLiveStore.getState().acknowledgeVoiceTransmission(id)
      void queryClient.invalidateQueries({ queryKey: ['voice-transmissions'] })
      setFeedbackMsg(language === 'en' ? 'Transmission marked as handled.' : 'Transmisi berhasil ditangani.')
      setTimeout(() => setFeedbackMsg(''), 4000)
    },
  })

  const broadcastAlarmMutation = useMutation({
    mutationFn: (id: string) =>
      api<{ message: string }>(`/voice/transmissions/${id}/broadcast-alarm`, {
        method: 'POST',
      }),
    onSuccess: (_data, id) => {
      useLiveStore.getState().updateVoiceTransmission({
        id,
        alarm_dispatched: true,
      } as VoiceTransmission)
      void queryClient.invalidateQueries({ queryKey: ['voice-transmissions'] })
      void queryClient.invalidateQueries({ queryKey: ['workers'] })
      setFeedbackMsg(
        language === 'en'
          ? 'Emergency alert buzzer sent to helmet.'
          : 'Alarm buzzer darurat berhasil dikirim ke helm.'
      )
      setTimeout(() => setFeedbackMsg(''), 4000)
    },
  })

  useEffect(() => {
    setIsPlaying(false)
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
  }, [activeTransmission?.id])

  const getAudioUrl = (transmission?: VoiceTransmission | null) => {
    if (!transmission) return ''
    if (transmission.audio_data_uri) {
      return transmission.audio_data_uri
    }
    const target = transmission.audio_url || '/api/v1/voice/latest-audio'
    if (target.startsWith('http://') || target.startsWith('https://') || target.startsWith('data:')) {
      return target
    }
    if (API_URL.startsWith('http://') || API_URL.startsWith('https://')) {
      const base = API_URL.replace(/\/api\/v1\/?$/, '')
      const path = target.startsWith('/') ? target : `/${target}`
      return `${base}${path}`
    }
    return target
  }

  const toggleAudio = () => {
    if (!audioRef.current) return
    if (isPlaying) {
      audioRef.current.pause()
      setIsPlaying(false)
    } else {
      audioRef.current.currentTime = 0
      audioRef.current.load()
      audioRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch((err) => {
          console.error('Audio play error:', err)
          setIsPlaying(false)
          setFeedbackMsg(
            language === 'en'
              ? 'Unable to play audio. Recording might have expired or connection failed.'
              : 'Gagal memutar audio. Rekaman mungkin telah kedaluwarsa atau terjadi gangguan koneksi.'
          )
          setTimeout(() => setFeedbackMsg(''), 4000)
        })
    }
  }

  const handleAudioEnded = () => {
    setIsPlaying(false)
  }

  const getUrgencyTone = (urgency: string) => {
    switch (urgency) {
      case 'CRITICAL':
        return { bg: '#fef2f2', border: '#fca5a5', text: '#dc2626', badgeBg: '#fee2e2' }
      case 'HIGH':
        return { bg: '#fff7ed', border: '#fdba74', text: '#ea580c', badgeBg: '#ffedd5' }
      case 'MODERATE':
        return { bg: '#fffbeb', border: '#fcd34d', text: '#d97706', badgeBg: '#fef3c7' }
      default:
        return { bg: '#f0fdf4', border: '#86efac', text: '#16a34a', badgeBg: '#dcfce7' }
    }
  }

  const tone = activeTransmission ? getUrgencyTone(activeTransmission.urgency) : null

  return (
    <section
      className="panel voice-dispatcher-panel"
      style={{
        borderColor: tone ? tone.border : undefined,
      }}
    >
      <div className="panel-header" style={{ paddingBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: '#0f78f618',
              color: '#0f78f6',
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
            }}
          >
            <Radio size={18} />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>
              {t.voice.panelTitle}
            </h3>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>
              {t.voice.panelSubtitle}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {allItems.length > 0 && (
            <button
              type="button"
              className="button secondary"
              style={{
                padding: '4px 10px',
                fontSize: '11px',
                height: 'auto',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
              }}
              onClick={() => setShowHistory(!showHistory)}
            >
              <History size={13} />
              <span>{showHistory ? t.voice.btnHideHistory : t.voice.btnShowHistory(allItems.length)}</span>
            </button>
          )}
        </div>
      </div>

      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {feedbackMsg && (
          <div
            style={{
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
              color: '#166534',
              padding: '8px 14px',
              borderRadius: '8px',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
            <span>{feedbackMsg}</span>
          </div>
        )}

        {!activeTransmission ? (
          <div
            style={{
              padding: '24px 16px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '6px',
              background: '#f8fafc',
              borderRadius: '8px',
              border: '1px dashed #cbd5e1',
            }}
          >
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                background: '#e2e8f0',
                display: 'grid',
                placeItems: 'center',
                color: '#64748b',
                marginBottom: '4px',
              }}
            >
              {allItems.length > 0 ? <CheckCircle2 size={18} style={{ color: '#16a34a' }} /> : <Mic size={18} />}
            </div>
            <strong style={{ color: 'var(--text)', fontSize: '14px' }}>
              {allItems.length > 0
                ? (language === 'en' ? 'All Voice Transmissions Handled' : 'Semua Transmisi Suara Telah Ditangani')
                : t.voice.emptyTitle}
            </strong>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)', maxWidth: '440px', lineHeight: 1.5 }}>
              {allItems.length > 0
                ? (language === 'en'
                    ? 'No open transmissions awaiting response. Review past calls in history anytime.'
                    : 'Tidak ada transmisi suara aktif yang menunggu respons. Periksa riwayat panggilan kapan saja.')
                : t.voice.emptyDesc}
            </p>
            {allItems.length > 0 && !showHistory && (
              <button
                type="button"
                className="button secondary"
                style={{ marginTop: '6px', padding: '4px 12px', fontSize: '12px', height: 'auto' }}
                onClick={() => setShowHistory(true)}
              >
                <History size={14} />
                <span>{language === 'en' ? `View History (${allItems.length})` : `Buka Riwayat (${allItems.length})`}</span>
              </button>
            )}
          </div>
        ) : (
          <div
            className="voice-card"
            style={{
              background: tone?.bg,
              border: `1px solid ${tone?.border}`,
            }}
          >
            {/* Header: Worker & Urgency Badges (Decluttered) */}
            <div className="voice-worker-header">
              <div className="voice-worker-info">
                <div className="voice-avatar">
                  {activeTransmission.worker_name
                    .split(' ')
                    .map((p) => p[0])
                    .slice(0, 2)
                    .join('')}
                </div>
                <div className="voice-worker-meta">
                  <div className="voice-worker-meta-top">
                    <span className="voice-worker-name">{activeTransmission.worker_name}</span>
                    <span className="voice-badge-id">{activeTransmission.worker_id}</span>
                    <span className="voice-location-tag">
                      <MapPin size={12} />
                      {activeTransmission.area}
                    </span>
                    {activeTransmission.target_hazard_name && (
                      <span
                        style={{
                          fontSize: '11px',
                          background: '#fff',
                          border: '1px solid #e2e8f0',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          color: '#475569',
                          fontWeight: 600,
                        }}
                      >
                        ⚠️ {activeTransmission.target_hazard_name}
                      </span>
                    )}
                  </div>
                  <small style={{ color: 'var(--muted)', fontSize: '11px' }}>
                    {t.voice.transmittedAt(formatDate(activeTransmission.timestamp, language))}
                  </small>
                </div>
              </div>

              <div className="voice-badges-right">
                <span
                  style={{
                    background: tone?.text,
                    color: '#fff',
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: '4px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    letterSpacing: '0.02em',
                  }}
                >
                  {activeTransmission.urgency === 'CRITICAL' ? (
                    <AlertOctagon size={12} />
                  ) : (
                    <AlertTriangle size={12} />
                  )}
                  {activeTransmission.urgency}
                </span>
                <span
                  style={{
                    background: '#ffffff',
                    border: '1px solid #cbd5e1',
                    fontSize: '11px',
                    fontWeight: 600,
                    padding: '3px 8px',
                    borderRadius: '4px',
                    color: 'var(--text)',
                  }}
                >
                  {activeTransmission.intent_label}
                </span>
              </div>
            </div>

            {/* Audio Transcription Card */}
            <div className="voice-audio-box">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--muted)', letterSpacing: '0.05em' }}>
                  {t.voice.transcriptionTitle}
                </span>
                <span style={{ fontSize: '11px', color: '#0f78f6', fontWeight: 600 }}>
                  {t.voice.nluAccuracy(Math.round(activeTransmission.confidence * 100))}
                </span>
              </div>

              <blockquote className="voice-quote">
                "{activeTransmission.transcription}"
              </blockquote>

              <div className="voice-player-row">
                <audio
                  ref={audioRef}
                  src={getAudioUrl(activeTransmission)}
                  preload="auto"
                  onEnded={handleAudioEnded}
                  onError={(e) => {
                    console.error('Audio element error on src:', audioRef.current?.src, e)
                    setIsPlaying(false)
                  }}
                  style={{ display: 'none' }}
                />
                {activeTransmission.audio_available || !!activeTransmission.audio_data_uri ? (
                  <button
                    type="button"
                    className="button secondary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 12px',
                      fontSize: '12px',
                      height: 'auto',
                      background: isPlaying ? '#0f78f6' : '#ffffff',
                      color: isPlaying ? '#ffffff' : '#0f78f6',
                      borderColor: '#0f78f6',
                    }}
                    onClick={toggleAudio}
                  >
                    {isPlaying ? <Pause size={14} /> : <Play size={14} />}
                    <span>{isPlaying ? t.voice.btnPauseAudio : t.voice.btnPlayAudio}</span>
                  </button>
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '11px',
                      color: 'var(--muted)',
                      background: '#f8fafc',
                      padding: '4px 10px',
                      borderRadius: '4px',
                      border: '1px solid #e2e8f0',
                    }}
                  >
                    <Mic size={14} />
                    <span>{t.voice.simulatedAudio}</span>
                  </div>
                )}
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--muted)' }}>
                  <Volume2 size={14} />
                  <span>{t.voice.audioSpecs(activeTransmission.audio_available)}</span>
                </div>
              </div>
            </div>

            {/* Recommendation Box */}
            <div
              className="voice-rec-card"
              style={{
                borderLeft: `3px solid ${tone?.text}`,
              }}
            >
              <ShieldAlert size={18} style={{ color: tone?.text, flexShrink: 0, marginTop: '2px' }} />
              <div>
                <strong style={{ fontSize: '12px', color: tone?.text, display: 'block' }}>
                  {t.voice.actionRecommendation}
                </strong>
                <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: '#1e293b', lineHeight: 1.45 }}>
                  {activeTransmission.recommended_action}
                </p>
              </div>
            </div>

            {/* Action Buttons Row */}
            <div className="voice-actions-row">
              <div className="voice-actions-btns">
                <button
                  type="button"
                  className="button danger"
                  disabled={broadcastAlarmMutation.isPending}
                  onClick={() => broadcastAlarmMutation.mutate(activeTransmission.id)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '12px',
                    padding: '8px 14px',
                  }}
                >
                  <BellRing size={15} />
                  <span>{t.voice.btnSendAlarm}</span>
                </button>

                {!activeTransmission.acknowledged && (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={acknowledgeMutation.isPending}
                    onClick={() => acknowledgeMutation.mutate(activeTransmission.id)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '12px',
                      padding: '8px 14px',
                    }}
                  >
                    <CheckCircle2 size={15} />
                    <span>{t.voice.btnMarkHandled}</span>
                  </button>
                )}
              </div>

              <div style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                {activeTransmission.alarm_dispatched && (
                  <span
                    style={{
                      background: '#fee2e2',
                      color: '#dc2626',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <BellRing size={12} />
                    {language === 'en' ? 'Buzzer Alert Sent' : 'Buzzer Terkirim'}
                  </span>
                )}
                <span
                  style={{
                    color: '#ea580c',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <Clock size={13} />
                  {t.voice.statusWaiting}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* History Table (Clean & Styled matching REKSA theme) */}
        {showHistory && allItems.length > 0 && (
          <div style={{ marginTop: '4px', borderTop: '1px solid #e2e8f0', paddingTop: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
              <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 700, color: 'var(--text)' }}>
                {t.voice.historyTitle(allItems.length)}
              </h4>
              <button
                type="button"
                className="button secondary"
                style={{ padding: '2px 8px', fontSize: '11px', height: 'auto' }}
                onClick={() => setShowHistory(false)}
              >
                {t.voice.btnHideHistory}
              </button>
            </div>

            <div className="table-wrap voice-history-table" style={{ maxHeight: '240px' }}>
              <table>
                <thead>
                  <tr>
                    <th>{language === 'en' ? 'Timestamp' : 'Waktu'}</th>
                    <th>{language === 'en' ? 'Worker' : 'Pekerja'}</th>
                    <th>{language === 'en' ? 'Area' : 'Area'}</th>
                    <th>{language === 'en' ? 'Urgency' : 'Urgensi'}</th>
                    <th>{language === 'en' ? 'Transcription' : 'Transkripsi'}</th>
                    <th>{language === 'en' ? 'Status' : 'Status'}</th>
                  </tr>
                </thead>
                <tbody>
                  {allItems.map((item) => (
                    <tr key={item.id}>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <small>{formatDate(item.timestamp, language)}</small>
                      </td>
                      <td>
                        <strong>{item.worker_name}</strong>
                        <small>{item.worker_id}</small>
                      </td>
                      <td>{item.area}</td>
                      <td>
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background:
                              item.urgency === 'CRITICAL'
                                ? '#fef2f2'
                                : item.urgency === 'HIGH'
                                ? '#fff7ed'
                                : '#f0fdf4',
                            color:
                              item.urgency === 'CRITICAL'
                                ? '#dc2626'
                                : item.urgency === 'HIGH'
                                ? '#ea580c'
                                : '#16a34a',
                          }}
                        >
                          {item.urgency}
                        </span>
                      </td>
                      <td style={{ maxWidth: '240px', whiteSpace: 'normal', fontStyle: 'italic', color: '#1e293b' }}>
                        "{item.transcription}"
                      </td>
                      <td>
                        {item.acknowledged ? (
                          <span
                            style={{
                              color: '#16a34a',
                              fontWeight: 600,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <CheckCircle2 size={13} />
                            {language === 'en' ? 'Handled' : 'Selesai'}
                          </span>
                        ) : (
                          <span
                            style={{
                              color: '#ea580c',
                              fontWeight: 600,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <Clock size={13} />
                            {language === 'en' ? 'Waiting' : 'Menunggu'}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
