import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Activity, ArrowLeft, ArrowLeftRight, Database, HeartPulse, LayoutDashboard, ListChecks, Menu, MessageSquare, Network, Settings as Cog, X,
} from 'lucide-react'
import { LogoMark } from '../components/Logo'
import { useSettings } from './SettingsContext'
import '../styles/console.css'

const NAV = [
  { to: 'overview', label: 'Overview', Icon: LayoutDashboard },
  { to: 'chat', label: 'Chat', Icon: MessageSquare },
  { to: 'memories', label: 'Memories', Icon: Database },
  { to: 'graph', label: 'Graph', Icon: Network },
  { to: 'tasks', label: 'Tasks', Icon: ListChecks },
  { to: 'runs', label: 'Runs', Icon: Activity },
  { to: 'handoffs', label: 'Handoffs', Icon: ArrowLeftRight },
  { to: 'health', label: 'Health', Icon: HeartPulse },
  { to: 'settings', label: 'Settings', Icon: Cog },
]

export default function ConsoleLayout() {
  const { settings } = useSettings()
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()

  useEffect(() => {
    // Close the mobile menu after navigating.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOpen(false)
    document.getElementById('console-main')?.focus({ preventScroll: true })
  }, [pathname])

  return (
    <div className="console" data-menu={open ? 'open' : 'closed'}>
      <a className="skip-link" href="#console-main">Skip to content</a>
      <aside className="console-side" aria-label="Console navigation">
        <Link to="/" className="brand"><LogoMark /> MemoryMesh</Link>
        <nav>
          <ul className="nav-list">
            {NAV.map(({ to, label, Icon }) => (
              <li key={to}>
                <NavLink to={`/app/${to}`} className={({ isActive }) => (isActive ? 'active' : '')}>
                  <Icon size={18} aria-hidden="true" /> {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="side-foot">
          <span>Prototype console. No sign-in is implied or required.</span>
          <Link to="/" className="muted"><ArrowLeft size={12} aria-hidden="true" /> Back to site</Link>
        </div>
      </aside>
      <button className="scrim" aria-label="Close menu" onClick={() => setOpen(false)} />
      <div className="console-main">
        <header className="topbar">
          <button className="btn btn-sm menu-btn" aria-expanded={open} aria-label={open ? 'Close menu' : 'Open menu'} onClick={() => setOpen((o) => !o)}>
            {open ? <X size={16} /> : <Menu size={16} />}
          </button>
          <span className={`badge ${settings.mode === 'demo' ? 'demo' : 'ok'}`} role="status">
            {settings.mode === 'demo' ? 'Demo data · not connected' : `API mode · ${settings.baseUrl || 'Proxy (localhost:8000)'}`}
          </span>
          <span className="spacer" />
          <span className="badge" title="Tenant and project sent with every backend call">
            {settings.tenantId} / {settings.projectId}
          </span>
        </header>
        <main id="console-main" tabIndex={-1} style={{ outline: 'none' }}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
