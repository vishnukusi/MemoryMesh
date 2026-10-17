import { useState } from 'react'
import { RefreshCw, CheckCircle2, AlertTriangle, XCircle, HelpCircle } from 'lucide-react'
import { useSettings } from '../../app/SettingsContext'
import { Async, StatusBadge } from '../../components/StateViews'
import { DemoNote, PageHead } from '../../components/PageHead'
import { useAsync } from '../../lib/useAsync'

function ServiceRow({
  name,
  note,
  status,
  details,
}: {
  name: string
  note?: string
  status: string
  details?: string
}) {
  const getIcon = () => {
    if (status === 'ok' || status === 'healthy' || status === 'connected') {
      return <CheckCircle2 size={16} color="var(--brand)" />
    }
    if (status === 'degraded') {
      return <AlertTriangle size={16} color="var(--brand-warm)" />
    }
    if (status === 'down' || status === 'unavailable') {
      return <XCircle size={16} color="#e5826f" />
    }
    return <HelpCircle size={16} className="muted" />
  }

  return (
    <div className="svc" style={{ padding: '14px 0', borderBottom: '1px solid var(--line)' }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {getIcon()}
          <span style={{ fontWeight: 500, color: 'var(--text)' }}>{name}</span>
        </div>
        {note && <small className="muted mono" style={{ display: 'block', fontSize: '.75rem', marginTop: 3 }}>{note}</small>}
        {details && <div style={{ fontSize: '.8125rem', marginTop: 4, color: 'var(--text-muted)' }}>{details}</div>}
      </div>
      <StatusBadge status={status} />
    </div>
  )
}

export default function HealthPage() {
  const { api, settings } = useSettings()
  const demo = api.mode === 'demo'
  const [checkedAt, setCheckedAt] = useState<string | null>(null)

  const state = useAsync(async () => {
    if (demo) return null
    const res = await api.health()
    setCheckedAt(new Date().toLocaleTimeString())
    return res
  }, `${api.mode}|${settings.baseUrl}`)

  return (
    <div className="page">
      <PageHead title="System Health">
        Diagnostic status of the FastAPI backend, FalkorDB graph database, and Ollama local language model.
      </PageHead>
      <DemoNote>
        Demo mode: no network health check is performed against live services. Switch to Live API in Settings to test FalkorDB and Ollama.
      </DemoNote>

      {demo ? (
        <section className="panel" aria-label="Services (not checked in demo)">
          <div style={{ marginBottom: 12 }}>
            <span className="badge demo">Demo mode active</span>
            <p className="muted" style={{ fontSize: '.875rem', marginTop: 6 }}>
              Services are not evaluated in demo mode. Connect to FastAPI to view real-time daemon statuses.
            </p>
          </div>
          <ServiceRow name="FastAPI Backend" note="http://localhost:8000" status="unknown" details="Unchecked in demo mode" />
          <ServiceRow name="FalkorDB Graph Store" note="Redis / Cypher protocol on port 6379" status="unknown" details="Unchecked in demo mode" />
          <ServiceRow name="Ollama LLM" note="Local inference on port 11434" status="unknown" details="qwen3:4b (demo representation only)" />
        </section>
      ) : (
        <Async state={state}>
          {(h) => {
            if (!h) return null
            const overallStatus = h.status === 'healthy' ? 'ok' : h.status === 'degraded' ? 'degraded' : 'down'

            return (
              <section className="panel" aria-label="Live backend services">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <h2 style={{ margin: 0, fontSize: '1.125rem' }}>Overall System State:</h2>
                      <StatusBadge status={overallStatus} />
                    </div>
                    {checkedAt && (
                      <p className="muted mono" style={{ fontSize: '.75rem', margin: '4px 0 0' }}>
                        Last checked: {checkedAt}
                      </p>
                    )}
                  </div>
                  <button className="btn btn-sm" onClick={state.reload}>
                    <RefreshCw size={13} aria-hidden="true" /> Re-check health
                  </button>
                </div>

                <div style={{ margin: '12px 0' }}>
                  <ServiceRow
                    name="FastAPI Backend Gateway"
                    note={`${settings.baseUrl || 'Local dev proxy'} · response status: "${h.status}"`}
                    status={h.status === 'healthy' ? 'ok' : h.status === 'degraded' ? 'ok' : 'down'}
                    details="Orchestrates Curator, Investigator, Planner, and Verifier agent pipeline."
                  />
                  <ServiceRow
                    name="FalkorDB Graph Database"
                    note="Redis protocol · Multi-tenant property graph"
                    status={h.falkordb}
                    details={
                      h.falkordb === 'ok'
                        ? 'Connected. Schemas and graph entities accessible.'
                        : 'Unavailable. Start with: docker run -p 6379:6379 falkordb/falkordb'
                    }
                  />
                  <ServiceRow
                    name="Ollama Local LLM Service"
                    note={h.model ? `Model specification: ${h.model}` : 'Model status unknown'}
                    status={h.ollama}
                    details={
                      h.ollama === 'ok'
                        ? `Running local model qwen3:4b.`
                        : 'Unavailable. Ensure Ollama daemon is running with qwen3:4b pulled.'
                    }
                  />
                </div>

                {h.tenants && h.tenants.length > 0 && (
                  <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--line)' }}>
                    <div className="label muted mono" style={{ fontSize: '.6875rem', marginBottom: 6 }}>
                      BACKEND AUTHORIZED TENANTS ({h.tenants.length})
                    </div>
                    <div className="chips">
                      {h.tenants.map((t) => (
                        <span key={t} className="badge mono">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )
          }}
        </Async>
      )}
    </div>
  )
}
