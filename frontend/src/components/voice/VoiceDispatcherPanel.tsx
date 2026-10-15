import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertOctagon,
  AlertTriangle,
  BellRing,
  CheckCircle2,
  MapPin,
  Mic,
  Pause,
  Play,
  Radio,
  ShieldAlert,
  Volume2,
} from 'lucide-react'
import { api } from '../../services/api'
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
    queryFn: () => api<{ items: VoiceTransmission[]; total: number; latest: VoiceTransmission | null; audio_available: boolean }>('/voice/transmissions'),
    refetchInterval: 5_000,
  })

  const liveLatest = useLiveStore((state) => state.latestTransmission)
  const activeTransmission: VoiceTransmission | null =
    liveLatest || transmissionsQuery.data?.latest || (transmissionsQuery.data?.items?.[0] ?? null)

  const acknowledgeMutation = useMutation({
    mutationFn: (id: string) =>
      api<VoiceTransmission>(`/voice/transmissions/${id}/acknowledge`, {
        method: 'POST',
        body: JSON.stringify({
          supervisor_note: language === 'en'
            ? 'Verified in command center and followed up'
            : 'Diverifikasi langsung di command center dan ditindaklanjuti',
          action_taken: 'VERIFIED_IN_PERSON',
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['voice-transmissions'] })
      setFeedbackMsg(t.voice.feedbackSuccess)
      setTimeout(() => setFeedbackMsg(''), 4000)
    },
  })

  const broadcastAlarmMutation = useMutation({
    mutationFn: (id: string) =>
      api<{ message: string }>(`/voice/transmissions/${id}/broadcast-alarm`, {
        method: 'POST',
      }),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ['voice-transmissions'] })
      void queryClient.invalidateQueries({ queryKey: ['workers'] })
      setFeedbackMsg(data.message || t.voice.feedbackAlarmSent)
      setTimeout(() => setFeedbackMsg(''), 4000)
    },
  })

  const toggleAudio = () => {
    if (!audioRef.current) return
    if (isPlaying) {
      audioRef.current.pause()
      setIsPlaying(false)
    } else {
      audioRef.current.currentTime = 0
      audioRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch(() => setIsPlaying(false))
    }
  }

  const handleAudioEnded = () => {
    setIsPlaying(false)
  }

  const getUrgencyTone = (urgency: string) => {
    switch (urgency) {
      case 'CRITICAL':
        return { bg: '#fef2f2', border: '#fca5a5', text: '#dc2626', badge: 'critical' }
      case 'HIGH':
        return { bg: '#fff7ed', border: '#fdba74', text: '#ea580c', badge: 'high' }
      case 'MODERATE':
        return { bg: '#fffbeb', border: '#fcd34d', text: '#d97706', badge: 'moderate' }
      default:
        return { bg: '#f0fdf4', border: '#86efac', text: '#16a34a', badge: 'safe' }
    }
  }

  const tone = activeTransmission ? getUrgencyTone(activeTransmission.urgency) : null

  return (
    <section className="panel voice-dispatcher-panel" style={{ border: tone ? `1px solid ${tone.border}` : undefined }}>
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
            }}
          >
            <Radio size={20} />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>{t.voice.panelTitle}</h3>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>
              {t.voice.panelSubtitle}
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {transmissionsQuery.data?.items && transmissionsQuery.data.items.length > 0 && (
            <button
              className="button secondary"
              style={{ padding: '4px 12px', fontSize: '12px', height: 'auto' }}
              onClick={() => setShowHistory(!showHistory)}
            >
              {showHistory ? t.voice.btnHideHistory : t.voice.btnShowHistory(transmissionsQuery.data.items.length)}
            </button>
          )}
        </div>
      </div>

      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {feedbackMsg && (
          <div
            style={{
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
              color: '#166534',
              padding: '8px 16px',
              borderRadius: '8px',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <CheckCircle2 size={16} />
            <span>{feedbackMsg}</span>
          </div>
        )}

        {!activeTransmission ? (
          <div
            style={{
              padding: '32px 16px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px',
              color: 'var(--muted)',
            }}
          >
            <Mic size={28} style={{ opacity: 0.4 }} />
            <strong style={{ color: 'var(--text)', fontSize: '16px' }}>{t.voice.emptyTitle}</strong>
            <p style={{ margin: 0, fontSize: '12px', maxWidth: '420px', lineHeight: 1.5 }}>
              {t.voice.emptyDesc}
            </p>
          </div>
        ) : (
          <div
            style={{
              background: tone?.bg,
              border: `1px solid ${tone?.border}`,
              borderRadius: '8px',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div
                  style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '8px',
                    background: '#0f78f6',
                    color: '#fff',
                    display: 'grid',
                    placeItems: 'center',
                    fontWeight: 700,
                    fontSize: '16px',
                  }}
                >
                  {activeTransmission.worker_name.split(' ').map((p) => p[0]).slice(0, 2).join('')}
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <strong style={{ fontSize: '16px' }}>{activeTransmission.worker_name}</strong>
                    <span style={{ fontSize: '12px', background: '#e2e8f0', padding: '4px 8px', borderRadius: '4px', fontWeight: 600 }}>
                      {activeTransmission.worker_id}
                    </span>
                    <span style={{ fontSize: '12px', color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <MapPin size={12} /> {activeTransmission.area}
                    </span>
                  </div>
                  <small style={{ color: 'var(--muted)', fontSize: '12px' }}>
                    {t.voice.transmittedAt(formatDate(activeTransmission.timestamp, language))}
                  </small>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    background: tone?.text,
                    color: '#fff',
                    fontSize: '12px',
                    fontWeight: 700,
                    padding: '4px 8px',
                    borderRadius: '4px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  {activeTransmission.urgency === 'CRITICAL' ? <AlertOctagon size={12} /> : <AlertTriangle size={12} />}
                  {activeTransmission.urgency}
                </span>
                <span
                  style={{
                    background: '#ffffff',
                    border: '1px solid #cbd5e1',
                    fontSize: '12px',
                    fontWeight: 600,
                    padding: '4px 8px',
                    borderRadius: '4px',
                    color: 'var(--text)',
                  }}
                >
                  {activeTransmission.intent_label}
                </span>
              </div>
            </div>

            <div
              style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                padding: '12px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--muted)', letterSpacing: '0.04em' }}>
                  {t.voice.transcriptionTitle}
                </span>
                <span style={{ fontSize: '12px', color: '#0f78f6', fontWeight: 600 }}>
                  {t.voice.nluAccuracy(Math.round(activeTransmission.confidence * 100))}
                </span>
              </div>

              <blockquote
                style={{
                  margin: 0,
                  fontSize: '16px',
                  fontWeight: 600,
                  color: '#0f172a',
                  fontStyle: 'italic',
                  lineHeight: 1.5,
                }}
              >
                "{activeTransmission.transcription}"
              </blockquote>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px', paddingTop: '8px', borderTop: '1px solid #f1f5f9', flexWrap: 'wrap' }}>
                <audio
                  ref={audioRef}
                  src={activeTransmission.audio_url || '/api/v1/voice/latest-audio'}
                  preload="none"
                  onEnded={handleAudioEnded}
                  style={{ display: 'none' }}
                />
                {activeTransmission.audio_available ? (
                  <button
                    type="button"
                    className="button secondary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 12px',
                      fontSize: '12px',
                      height: 'auto',
                      background: isPlaying ? '#0f78f6' : '#ffffff',
                      color: isPlaying ? '#ffffff' : '#0f78f6',
                      borderColor: '#0f78f6',
                    }}
                    onClick={toggleAudio}
                  >
                    {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                    <span>{isPlaying ? t.voice.btnPauseAudio : t.voice.btnPlayAudio}</span>
                  </button>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--muted)', background: '#f8fafc', padding: '4px 12px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
                    <Mic size={16} />
                    <span>{t.voice.simulatedAudio}</span>
                  </div>
                )}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--muted)' }}>
                  <Volume2 size={16} />
                  <span>{t.voice.audioSpecs(activeTransmission.audio_available)}</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)' }}>{t.voice.detectedEntities}</span>
              {activeTransmission.target_hazard_name && (
                <span
                  style={{
                    background: '#ffffff',
                    border: '1px solid #e2e8f0',
                    fontSize: '12px',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontWeight: 600,
                  }}
                >
                  {t.voice.relatedHazard} <strong>{activeTransmission.target_hazard_name}</strong> ({activeTransmission.target_hazard_id})
                </span>
              )}
              <span
                style={{
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  fontSize: '12px',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontWeight: 600,
                }}
              >
                {t.voice.location} <strong>{activeTransmission.area}</strong>
              </span>
              <span
                style={{
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  fontSize: '12px',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontWeight: 600,
                }}
              >
                {t.voice.classification} <strong>{activeTransmission.nature}</strong>
              </span>
            </div>

            <div
              style={{
                background: '#ffffff',
                borderLeft: `4px solid ${tone?.text}`,
                padding: '8px 12px',
                borderRadius: '0 8px 8px 0',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
              }}
            >
              <ShieldAlert size={20} style={{ color: tone?.text, flexShrink: 0, marginTop: '2px' }} />
              <div>
                <strong style={{ fontSize: '12px', color: tone?.text }}>{t.voice.actionRecommendation}</strong>
                <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: '#1e293b', lineHeight: 1.4 }}>
                  {activeTransmission.recommended_action}
                </p>
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '8px',
                paddingTop: '4px',
              }}
            >
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="button danger"
                  disabled={broadcastAlarmMutation.isPending}
                  onClick={() => broadcastAlarmMutation.mutate(activeTransmission.id)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '12px', padding: '8px 16px' }}
                >
                  <BellRing size={16} />
                  <span>{t.voice.btnSendAlarm}</span>
                </button>

                {!activeTransmission.acknowledged && (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={acknowledgeMutation.isPending}
                    onClick={() => acknowledgeMutation.mutate(activeTransmission.id)}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '12px', padding: '8px 16px' }}
                  >
                    <CheckCircle2 size={16} />
                    <span>{t.voice.btnMarkHandled}</span>
                  </button>
                )}
              </div>

              <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                {activeTransmission.acknowledged ? (
                  <span style={{ color: '#16a34a', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    <CheckCircle2 size={16} /> {t.voice.statusHandled}
                  </span>
                ) : (
                  <span style={{ color: '#ea580c', fontWeight: 600 }}>{t.voice.statusWaiting}</span>
                )}
              </div>
            </div>
          </div>
        )}

        {showHistory && transmissionsQuery.data?.items && (
          <div style={{ marginTop: '8px', borderTop: '1px solid #e2e8f0', paddingTop: '16px' }}>
            <h4 style={{ margin: '0 0 12px 0', fontSize: '12px', fontWeight: 700, color: 'var(--text)' }}>
              {t.voice.historyTitle(transmissionsQuery.data.items.length)}
            </h4>
            <div className="table-wrap" style={{ maxHeight: '220px', overflowY: 'auto' }}>
              <table style={{ fontSize: '12px' }}>
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
                  {transmissionsQuery.data.items.map((item) => (
                    <tr key={item.id}>
                      <td><small>{formatDate(item.timestamp, language)}</small></td>
                      <td><strong>{item.worker_name}</strong><br /><small>{item.worker_id}</small></td>
                      <td>{item.area}</td>
                      <td>
                        <span
                          style={{
                            fontSize: '12px',
                            fontWeight: 700,
                            padding: '4px 8px',
                            borderRadius: '4px',
                            background: item.urgency === 'CRITICAL' ? '#fef2f2' : item.urgency === 'HIGH' ? '#fff7ed' : '#f0fdf4',
                            color: item.urgency === 'CRITICAL' ? '#dc2626' : item.urgency === 'HIGH' ? '#ea580c' : '#16a34a',
                          }}
                        >
                          {item.urgency}
                        </span>
                      </td>
                      <td style={{ maxWidth: '280px', whiteSpace: 'normal' }}>
                        "{item.transcription}"
                      </td>
                      <td>
                        {item.acknowledged ? (
                          <span style={{ color: '#16a34a', fontWeight: 600 }}>
                            {language === 'en' ? 'Resolved' : 'Selesai'}
                          </span>
                        ) : (
                          <span style={{ color: '#ea580c', fontWeight: 600 }}>
                            {language === 'en' ? 'Open' : 'Terbuka'}
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
