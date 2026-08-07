import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, Bell, ChevronLeft, ChevronRight, HardHat, LayoutDashboard, Menu, Radio, Settings,
  X, Users
} from 'lucide-react'
import { useLiveSocket } from '../hooks/useLiveSocket'
import { useLiveStore } from '../stores/liveStore'
import { api } from '../services/api'

const nav = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/live', label: 'Live Monitoring', icon: Radio },
  { to: '/workers', label: 'Workers', icon: Users },
  { to: '/settings', label: 'Settings', icon: Settings },
]

const titles: Record<string, string> = {
  '/': 'Overview',
  '/live': 'Live Monitoring',
  '/workers': 'Workers Directory',
  '/settings': 'System Settings',
}

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [clock, setClock] = useState(new Date())
  const location = useLocation()
  const notificationCount = useLiveStore((state) => state.notificationCount)
  const clearNotifications = useLiveStore((state) => state.clearNotifications)
  useLiveSocket()

  const summaryQuery = useQuery({
    queryKey: ['summary'],
    queryFn: () => api<{ connected_devices: number; total_devices: number }>('/dashboard/summary'),
    refetchInterval: 10_000,
  })

  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const pageTitle = location.pathname.startsWith('/workers/') ? 'Worker Risk Profile' : titles[location.pathname] ?? 'REKSA'

  return (
    <div className={`app-shell ${collapsed ? 'is-collapsed' : ''}`}>
      {mobileOpen && <button className="mobile-overlay" aria-label="Tutup menu" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark"><HardHat size={23} strokeWidth={2.4} /></div>
          <div className="brand-copy"><strong>REKSA</strong><span>Safety Monitoring</span></div>
          <button className="mobile-close" onClick={() => setMobileOpen(false)}><X size={20} /></button>
        </div>

        <nav>
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'} onClick={() => setMobileOpen(false)} title={collapsed ? label : undefined}>
              <Icon size={18} /><span>{label}</span>{label === 'Near Miss' && notificationCount > 0 && <b>{notificationCount}</b>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="system-mini"><div><strong>System Operational</strong><small>{summaryQuery.data ? `${summaryQuery.data.connected_devices} / ${summaryQuery.data.total_devices} devices online` : 'Memuat status...'}</small></div></div>
          <button className="collapse-button" onClick={() => setCollapsed(!collapsed)}>{collapsed ? <ChevronRight size={17} /> : <><ChevronLeft size={17} /> Ciutkan sidebar</>}</button>
        </div>
      </aside>
      <main className="main-shell">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileOpen(true)}><Menu size={20} /></button>
          <div className="page-heading"><h1>{pageTitle}</h1></div>
          <div className="topbar-meta">
            <div className="clock"><strong>{clock.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</strong><span>{clock.toLocaleDateString('id-ID', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })}</span></div>
            <div className="connection-group"></div>
            <button className="icon-button notification" aria-label="Notifikasi" onClick={clearNotifications}><Bell size={19} />{notificationCount > 0 && <b>{notificationCount}</b>}</button>
            <div className="profile"><span>RW</span><div><strong>Raka Wijaya</strong><small>Supervisor K3</small></div></div>
          </div>
        </header>
        <div className="page-content"><Outlet /></div>
        <footer className="footer"><span><Activity size={13} /> REKSA v1.0 · Industrial Safety Monitoring System</span><span>Dynamic Hazard Awareness and Near-Miss Tracking</span></footer>
      </main>
    </div>
  )
}
