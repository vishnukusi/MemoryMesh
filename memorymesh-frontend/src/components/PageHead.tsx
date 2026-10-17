import { Info } from 'lucide-react'
import { useSettings } from '../app/SettingsContext'

export function PageHead({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <header className="page-head">
      <h1>{title}</h1>
      {children && <p>{children}</p>}
    </header>
  )
}

/** Shown in demo mode so nobody mistakes mock data for a live backend. */
export function DemoNote({ children }: { children?: React.ReactNode }) {
  const { settings } = useSettings()
  if (settings.mode !== 'demo') return null
  return (
    <div className="demo-note" role="note">
      <Info size={16} aria-hidden="true" style={{ flex: 'none', marginTop: 2 }} />
      <span>{children ?? 'Demo mode: deterministic sample data, held in browser memory only. Nothing is sent to a backend.'}</span>
    </div>
  )
}
