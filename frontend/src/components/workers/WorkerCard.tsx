import { useState } from 'react'
import { Activity, BellRing, Check, Clock3, Droplets, Radio, Thermometer, Wifi, WifiOff, Wind } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Worker } from '../../types'
import { RiskBadge } from '../common/RiskBadge'
import { useTranslation } from '../../i18n'

export function WorkerCard({
  worker,
  onMarkSafe,
  onTestHelmet,
}: {
  worker: Worker
  onMarkSafe?: () => void
  onTestHelmet?: () => void
}) {
  const [isRinging, setIsRinging] = useState(false)
  const isCritical = worker.risk_level === 'CRITICAL'
  const isOnline = worker.online

  const { t, language } = useTranslation()

  const handleTestHelmet = () => {
    if (!onTestHelmet || isRinging) return
    setIsRinging(true)
    onTestHelmet()
    setTimeout(() => {
      setIsRinging(false)
    }, 1500)
  }

  return (
    <article
      className={`worker-card risk-border-${isOnline ? worker.risk_level.toLowerCase() : 'offline'} ${isCritical ? 'critical-card' : ''}`}
      style={!isOnline ? { opacity: 0.6 } : undefined}
    >
      <div className="worker-card-head">
        <div className="avatar">
          {worker.name
            .split(' ')
            .map((part) => part[0])
            .slice(0, 2)
            .join('')}
        </div>
        <div className="worker-card-meta">
          <Link to={`/workers/${worker.id}`} className="worker-card-name">{worker.name}</Link>
          <span className="worker-card-area">
            {worker.id} · {worker.area}
          </span>
        </div>
        <div className="worker-card-actions">
          {isOnline && onTestHelmet && (
            <button
              onClick={handleTestHelmet}
              className={`action-btn ${isRinging ? 'action-btn-ringing' : ''}`}
              title={isRinging ? t.live.buzzerSuccess : t.live.cardBuzzerTest}
              aria-label={t.live.cardBuzzerTest}
              disabled={isRinging}
            >
              {isRinging ? <Check size={16} className="btn-success-icon" /> : <BellRing size={16} className="btn-bell-icon" />}
            </button>
          )}
          {isOnline ? (
            <RiskBadge level={worker.risk_level} />
          ) : (
            <span className="offline-badge">{t.common.offline}</span>
          )}
        </div>
      </div>

      <div className="risk-score-row">
        <div className="risk-score-label-wrap">
          <span className="risk-score-title">{t.live.cardRiskScore.toUpperCase()}</span>
          <div className="risk-score-numbers">
            <strong>{isOnline ? worker.risk_score : '-'}</strong>
            <small>/100</small>
          </div>
        </div>
        <div className="score-track">
          <i style={{ width: `${isOnline ? worker.risk_score : 0}%` }} />
        </div>
      </div>

      <div className="hazard-box">
        <div className="hazard-box-top">
          <div className="hazard-label-wrap">
            <Radio size={16} className="hazard-radio-icon" />
            <span className="hazard-heading">{t.live.cardHazardNearby}</span>
          </div>
          <div className="hazard-badge-wrap">
            {worker.hazard_category && (
              <span className={`hazard-cat-pill ${worker.hazard_category.toLowerCase()}`}>
                {worker.hazard_category}
              </span>
            )}
            <span className="hazard-rssi-pill">
              {isOnline ? `${worker.rssi} dBm` : '-'}
            </span>
          </div>
        </div>
        <div className="hazard-box-bottom">
          <strong className="hazard-name-text">
            {isOnline ? (worker.hazard_name || t.live.cardNoHazard) : '-'}
          </strong>
          {isOnline && worker.hazard_status && (
            <span className="hazard-status-pill">{worker.hazard_status}</span>
          )}
        </div>
      </div>

      <div className="worker-grid">
        <div className="metric-pill">
          <span className="metric-label">
            <Clock3 size={16} /> {language === 'en' ? 'Exposure' : 'Paparan'}
          </span>
          <b className="metric-val">{isOnline ? `${worker.exposure_seconds} ${language === 'en' ? 's' : 'dtk'}` : '-'}</b>
        </div>
        <div className="metric-pill">
          <span className="metric-label">
            <Thermometer size={16} /> {t.live.cardTemp}
          </span>
          <b className="metric-val">{isOnline ? `${worker.temperature}°C` : '-'}</b>
        </div>
        <div className="metric-pill">
          <span className="metric-label">
            <Droplets size={16} /> {language === 'en' ? 'Humidity' : 'Lembap'}
          </span>
          <b className="metric-val">{isOnline ? `${worker.humidity}%` : '-'}</b>
        </div>
        <div className="metric-pill">
          <span className="metric-label">
            <Wind size={16} /> {t.live.cardAir}
          </span>
          <b className="metric-val">{isOnline ? worker.air_quality_level : '-'}</b>
        </div>
        <div className="metric-pill">
          <span className="metric-label">
            <Activity size={16} /> {language === 'en' ? 'Impact' : 'Benturan'}
          </span>
          <b className="metric-val">{isOnline ? `${(worker.impact_g ?? 1.0).toFixed(1)}g` : '-'}</b>
        </div>
        <div className="metric-pill">
          <span className="metric-label">
            {isOnline ? <Wifi size={16} /> : <WifiOff size={16} />} {t.common.status}
          </span>
          <b className={`metric-val ${isOnline ? 'status-online' : 'status-offline'}`}>
            {isOnline ? t.common.online : t.common.offline}
          </b>
        </div>
      </div>

      {isCritical && (
        <div className="critical-actions">
          <span>
            <i className="pulse-dot" /> {language === 'en' ? 'IMMEDIATE ACTION REQUIRED' : 'TINDAKAN SEGERA DIPERLUKAN'}
          </span>
          {onMarkSafe && <button onClick={onMarkSafe}>{t.live.cardMarkSafe}</button>}
        </div>
      )}
    </article>
  )
}

