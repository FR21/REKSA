import { useEffect, useRef, useState, useMemo } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, Bell, ChevronLeft, ChevronRight, HardHat, LayoutDashboard, Menu, Radio, Settings,
  ShieldAlert, Users, X, User, Check
} from 'lucide-react'
import { useLiveSocket } from '../hooks/useLiveSocket'
import { useLiveStore } from '../stores/liveStore'
import { useProfile } from '../hooks/useProfile'
import { useTranslation } from '../i18n'
import { api } from '../services/api'

export function AppLayout() {
  const { t, language, setLanguage } = useTranslation()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [clock, setClock] = useState(new Date())
  const location = useLocation()
  const [notificationOpen, setNotificationOpen] = useState(false)
  const [profileModalOpen, setProfileModalOpen] = useState(false)
  const notifRef = useRef<HTMLDivElement | null>(null)

  // Profile synced with Backend DB & WebSocket
  const { profile, updateProfile, isUpdating } = useProfile()
  const [editName, setEditName] = useState(profile.name)
  const [editRole, setEditRole] = useState(profile.role)

  const notificationCount = useLiveStore((state) => state.notificationCount)
  const notifications = useLiveStore((state) => state.notifications)
  const clearNotifications = useLiveStore((state) => state.clearNotifications)
  useLiveSocket()

  // Close notification dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotificationOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const summaryQuery = useQuery({
    queryKey: ['summary'],
    queryFn: () => api<{ connected_devices: number; total_devices: number }>('/dashboard/summary'),
    refetchInterval: 10_000,
  })

  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const handleProfileSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editName.trim()) return

    try {
      await updateProfile({
        name: editName.trim(),
        role: editRole.trim() || 'Supervisor K3',
      })
      setProfileModalOpen(false)
    } catch (err) {
      console.error('Failed to update profile:', err)
    }
  }

  const nav = useMemo(
    () => [
      { to: '/', label: t.nav.overview, icon: LayoutDashboard },
      { to: '/live', label: t.nav.live, icon: Radio },
      { to: '/near-misses', label: t.nav.nearMiss, icon: ShieldAlert },
      { to: '/workers', label: t.nav.workers, icon: Users },
      { to: '/settings', label: t.nav.settings, icon: Settings },
    ],
    [t.nav]
  )

  const titles: Record<string, string> = useMemo(
    () => ({
      '/': t.pageTitles.overview,
      '/live': t.pageTitles.live,
      '/near-misses': t.pageTitles.nearMiss,
      '/workers': t.pageTitles.workers,
      '/settings': t.pageTitles.settings,
    }),
    [t.pageTitles]
  )

  const pageTitle = location.pathname.startsWith('/workers/')
    ? t.pageTitles.workerDetail
    : titles[location.pathname] ?? 'REKSA'

  return (
    <div className={`app-shell ${collapsed ? 'is-collapsed' : ''}`}>
      {mobileOpen && <button className="mobile-overlay" aria-label={t.common.close} onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark"><HardHat size={22} strokeWidth={2.4} /></div>
          <div className="brand-copy"><strong>REKSA</strong><span>{t.nav.brandSubtitle}</span></div>
        </div>

        <nav>
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'} onClick={() => setMobileOpen(false)} title={collapsed ? label : undefined}>
              <Icon size={20} /><span>{label}</span>{to === '/near-misses' && notificationCount > 0 && <b>{notificationCount}</b>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="system-mini" title={summaryQuery.data ? `${summaryQuery.data.connected_devices} / ${summaryQuery.data.total_devices} ${t.nav.devicesOnline}` : t.common.systemOperational}>
            <span className="live-dot" />
            <div className="system-mini-text">
              <strong>{t.common.systemOperational}</strong>
              <small>{summaryQuery.data ? `${summaryQuery.data.connected_devices} / ${summaryQuery.data.total_devices} ${t.nav.devicesOnline}` : t.common.loading}</small>
            </div>
          </div>
          <button className="collapse-button" onClick={() => setCollapsed(!collapsed)} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {collapsed ? <ChevronRight size={16} /> : <><ChevronLeft size={16} /> {language === 'id' ? 'Ciutkan sidebar' : 'Collapse sidebar'}</>}
          </button>
        </div>
      </aside>
      <main className="main-shell">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileOpen(true)}><Menu size={20} /></button>
          <div className="page-heading"><h1>{pageTitle}</h1></div>
          <div className="topbar-meta">
            <div className="clock">
              <strong>{clock.toLocaleTimeString(language === 'id' ? 'id-ID' : 'en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</strong>
              <span>{clock.toLocaleDateString(language === 'id' ? 'id-ID' : 'en-US', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })}</span>
            </div>

            {/* LANGUAGE SWITCHER */}
            <div className="lang-switcher" role="group" aria-label={t.common.languageSelect}>
              <button
                type="button"
                className={`lang-btn ${language === 'id' ? 'is-active' : ''}`}
                onClick={() => setLanguage('id')}
                title="Bahasa Indonesia"
              >
                ID
              </button>
              <button
                type="button"
                className={`lang-btn ${language === 'en' ? 'is-active' : ''}`}
                onClick={() => setLanguage('en')}
                title="English"
              >
                EN
              </button>
            </div>
            
            <div className="notification-wrapper" ref={notifRef}>
              <button
                className={`icon-button notification ${notificationOpen ? 'is-open' : ''} ${notificationCount > 0 ? 'has-unread' : ''}`}
                aria-label={t.notifications.title}
                title={t.notifications.tooltip}
                onClick={() => setNotificationOpen(!notificationOpen)}
              >
                <Bell size={20} />
                {notificationCount > 0 && <b>{notificationCount}</b>}
              </button>

              {notificationOpen && (
                <div className="notification-dropdown">
                  <div className="notification-header">
                    <h4>{t.notifications.title}</h4>
                    {notifications.some(n => !n.read) && (
                      <button className="clear-btn" onClick={() => clearNotifications()}>{t.notifications.clearAll}</button>
                    )}
                  </div>
                  <div className="notification-list">
                    {notifications.length === 0 ? (
                      <div className="empty-notif">{t.notifications.empty}</div>
                    ) : (
                      notifications.map((n) => (
                        <div key={n.id} className={`notif-item ${n.read ? 'read' : 'unread'}`}>
                          <p>{n.message}</p>
                          <time>{n.time}</time>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            <div
              className="profile"
              onClick={() => {
                setEditName(profile.name)
                setEditRole(profile.role)
                setProfileModalOpen(true)
              }}
              title={t.profileModal.tooltip}
            >
              <span>{profile.initials}</span>
              <div>
                <strong>{profile.name}</strong>
                <small>{profile.role}</small>
              </div>
            </div>
          </div>
        </header>

        <div className="page-content"><Outlet /></div>
        <footer className="footer">
          <span><Activity size={16} /> {t.nav.footerSystem}</span>
          <span>{t.nav.footerDesc}</span>
        </footer>
      </main>

      {/* MODAL EDIT PROFIL */}
      {profileModalOpen && (
        <div className="modal-backdrop" onClick={() => setProfileModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <User size={18} style={{ color: 'var(--blue)' }} />
                <h3>{t.profileModal.title}</h3>
              </div>
              <button
                type="button"
                className="action-btn"
                onClick={() => setProfileModalOpen(false)}
                title={t.common.close}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <form onSubmit={handleProfileSave} className="device-form">
                <label>
                  <span>{t.profileModal.fullName}</span>
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder={t.profileModal.fullNamePlaceholder}
                    required
                    autoFocus
                  />
                </label>

                <label>
                  <span>{t.profileModal.role}</span>
                  <select
                    value={editRole}
                    onChange={(e) => setEditRole(e.target.value)}
                  >
                    <option value="Supervisor K3">{t.profileModal.roles.supervisor}</option>
                    <option value="HSE Manager">{t.profileModal.roles.manager}</option>
                    <option value="Safety Officer">{t.profileModal.roles.officer}</option>
                    <option value="Plant Operations Lead">{t.profileModal.roles.operations}</option>
                    <option value="Admin Sistem">{t.profileModal.roles.admin}</option>
                  </select>
                </label>

                <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => setProfileModalOpen(false)}
                    style={{ flex: 1 }}
                  >
                    {t.common.cancel}
                  </button>
                  <button
                    type="submit"
                    className="button primary"
                    style={{ flex: 2 }}
                    disabled={isUpdating}
                  >
                    <Check size={16} /> {isUpdating ? t.profileModal.saving : t.profileModal.save}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
