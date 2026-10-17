import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Settings } from '../types'
import { createHttpApi } from '../lib/api/http'
import type { Api } from '../lib/api/types'
import { createMockApi } from '../lib/mock/mockApi'
import { DEMO_PROJECT } from '../lib/mock/data'

const env = import.meta.env as Record<string, string | undefined>
const KEY = 'memorymesh.settings.v1'

export const ALLOWED_TENANTS = ['tenant_alpha', 'tenant_beta'] as const
export type AllowedTenant = (typeof ALLOWED_TENANTS)[number]

const defaults: Settings = {
  mode: env.VITE_DEFAULT_MODE === 'api' ? 'api' : 'demo',
  // Default to empty string so requests route through the Vite dev proxy to http://localhost:8000 without CORS
  baseUrl: env.VITE_API_BASE_URL ?? '',
  tenantId: env.VITE_DEFAULT_TENANT_ID || 'tenant_alpha',
  projectId: DEMO_PROJECT,
  reduceMotion: false,
}

function getStoredSessionId(): string {
  try {
    let sid = sessionStorage.getItem('memorymesh.session_id')
    if (!sid) {
      sid = `sess_${crypto.randomUUID().slice(0, 8)}`
      sessionStorage.setItem('memorymesh.session_id', sid)
    }
    return sid
  } catch {
    return 'sess_default'
  }
}

// Only non-secret preferences are stored. Never add tokens or API keys here.
function load(): Settings {
  try {
    const raw = localStorage.getItem(KEY)
    const parsed = raw ? (JSON.parse(raw) as Partial<Settings>) : {}
    const merged = { ...defaults, ...parsed }
    if (merged.mode === 'api' && !ALLOWED_TENANTS.includes(merged.tenantId as AllowedTenant)) {
      merged.tenantId = 'tenant_alpha'
    }
    return merged
  } catch {
    return defaults
  }
}

interface Ctx {
  settings: Settings
  update: (patch: Partial<Settings>) => void
  api: Api
  /** true when the OS or the in-app preference asks for reduced motion */
  reducedMotion: boolean
  sessionId: string
  newSession: () => string
}
const SettingsCtx = createContext<Ctx | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(load)
  const [sessionId, setSessionId] = useState<string>(getStoredSessionId)
  const [osReduce, setOsReduce] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const on = () => setOsReduce(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(settings))
    } catch {
      /* storage unavailable */
    }
  }, [settings])

  const newSession = () => {
    const next = `sess_${crypto.randomUUID().slice(0, 8)}`
    try {
      sessionStorage.setItem('memorymesh.session_id', next)
    } catch {
      /* ignore */
    }
    setSessionId(next)
    return next
  }

  // One mock instance per mode switch so demo edits survive navigation but reset when switching.
  const api = useMemo(
    () => (settings.mode === 'api' ? createHttpApi(settings.baseUrl) : createMockApi()),
    [settings.mode, settings.baseUrl],
  )
  const reducedMotion = osReduce || settings.reduceMotion

  useEffect(() => {
    document.documentElement.dataset.reduceMotion = reducedMotion ? 'true' : 'false'
  }, [reducedMotion])

  const value = useMemo(
    () => ({
      settings,
      update: (p: Partial<Settings>) => setSettings((s) => ({ ...s, ...p })),
      api,
      reducedMotion,
      sessionId,
      newSession,
    }),
    [settings, api, reducedMotion, sessionId],
  )
  return <SettingsCtx.Provider value={value}>{children}</SettingsCtx.Provider>
}

export function useSettings() {
  const c = useContext(SettingsCtx)
  if (!c) throw new Error('useSettings must be used inside SettingsProvider')
  return c
}
