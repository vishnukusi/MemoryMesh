import { useState } from 'react'
import { useSettings, ALLOWED_TENANTS } from '../../app/SettingsContext'
import { Async, StatusBadge } from '../../components/StateViews'
import { DemoNote, PageHead } from '../../components/PageHead'
import { useAsync } from '../../lib/useAsync'

function RunDetail({ id }: { id: string }) {
  const { api, settings } = useSettings()
  const state = useAsync(() => api.run(id, settings.tenantId), `${api.mode}|${id}|${settings.tenantId}`)

  return (
    <article className="panel" aria-label="Run detail">
      <Async state={state}>
        {(run) => {
          const duration =
            run.startedAt && run.completedAt
              ? `${Math.max(0, Math.round((new Date(run.completedAt).getTime() - new Date(run.startedAt).getTime()) / 1000))}s`
              : null

          return (
            <>
              <div className="chips" style={{ marginBottom: 12 }}>
                <StatusBadge status={run.status} />
                <span className="badge mono">{run.id}</span>
                {run.agentName && <span className="badge">{run.agentName}</span>}
              </div>

              <h2 style={{ textTransform: 'none', letterSpacing: 0, fontFamily: 'var(--font)', fontSize: '1.25rem', color: 'var(--text)' }}>
                {run.goal || run.query}
              </h2>

              {run.summary && <p style={{ margin: '12px 0', fontSize: '.9375rem', lineHeight: 1.5 }}>{run.summary}</p>}

              {run.error && (
                <div className="panel" style={{ background: 'rgba(229,130,111,.08)', border: '1px solid rgba(229,130,111,.3)', color: '#e5826f', margin: '12px 0', padding: 12 }}>
                  <b>Error:</b> {run.error}
                </div>
              )}

              <div className="grid cols-2" style={{ gap: 12, marginTop: 16 }}>
                <div className="panel" style={{ padding: 12, background: 'rgba(255,255,255,.02)' }}>
                  <div className="mono muted" style={{ fontSize: '.6875rem', marginBottom: 4 }}>STARTED AT</div>
                  <div style={{ fontSize: '.875rem' }}>{run.startedAt ? run.startedAt.replace('T', ' ').slice(0, 19) : 'Not recorded'}</div>
                </div>
                <div className="panel" style={{ padding: 12, background: 'rgba(255,255,255,.02)' }}>
                  <div className="mono muted" style={{ fontSize: '.6875rem', marginBottom: 4 }}>COMPLETED / DURATION</div>
                  <div style={{ fontSize: '.875rem' }}>
                    {run.completedAt ? run.completedAt.replace('T', ' ').slice(0, 19) : 'In progress / Not provided'}
                    {duration ? ` (${duration})` : ''}
                  </div>
                </div>
                <div className="panel" style={{ padding: 12, background: 'rgba(255,255,255,.02)' }}>
                  <div className="mono muted" style={{ fontSize: '.6875rem', marginBottom: 4 }}>RECORDS READ</div>
                  <div style={{ fontSize: '.8125rem' }}>
                    {run.recordsRead && run.recordsRead.length > 0
                      ? run.recordsRead.join(', ')
                      : <span className="muted">Not provided by API</span>}
                  </div>
                </div>
                <div className="panel" style={{ padding: 12, background: 'rgba(255,255,255,.02)' }}>
                  <div className="mono muted" style={{ fontSize: '.6875rem', marginBottom: 4 }}>RECORDS WRITTEN</div>
                  <div style={{ fontSize: '.8125rem' }}>
                    {run.recordsWritten && run.recordsWritten.length > 0
                      ? run.recordsWritten.join(', ')
                      : <span className="muted">Not provided by API</span>}
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 18 }}>
                <div className="label muted mono" style={{ fontSize: '.6875rem', marginBottom: 8 }}>AGENT TRACE STEPS</div>
                {run.traces.length === 0 ? (
                  <p className="muted" style={{ fontSize: '.8125rem' }}>No individual step traces returned for this run entity.</p>
                ) : (
                  <ol className="trace" style={{ margin: 0, padding: 0 }}>
                    {run.traces.map((t, i) => (
                      <li key={i}>
                        <b>{t.agent}</b>
                        <span className="mono muted">{t.action}</span>
                        <div className="muted">{t.summary}</div>
                        {t.evidenceIds && t.evidenceIds.length > 0 && (
                          <div className="chips" style={{ marginTop: 6 }}>
                            {t.evidenceIds.map((e) => (
                              <span key={e} className="pill" style={{ cursor: 'default' }}>
                                {e}
                              </span>
                            ))}
                          </div>
                        )}
                        {t.durationMs !== undefined && (
                          <span className="mono muted" style={{ fontSize: '.6875rem' }}>
                            {t.durationMs} ms
                          </span>
                        )}
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </>
          )
        }}
      </Async>
    </article>
  )
}

export default function RunsPage() {
  const { api, settings, update } = useSettings()
  const state = useAsync(() => api.runs(settings.tenantId, 25), `${api.mode}|${settings.baseUrl}|${settings.tenantId}`)
  const [sel, setSel] = useState<string | null>(null)

  return (
    <div className="page">
      <PageHead title="Agent runs">
        Each run records which specialist did what, and which memory records were consulted.
      </PageHead>
      <DemoNote />

      {/* Tenant Selector */}
      <div className="panel" style={{ padding: '10px 16px', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <label htmlFor="runs-tenant" className="label mono muted" style={{ fontSize: '.75rem' }}>TENANT</label>
          {settings.mode === 'api' ? (
            <select
              id="runs-tenant"
              className="input"
              style={{ padding: '4px 10px', fontSize: '.8125rem', width: 'auto' }}
              value={settings.tenantId}
              onChange={(e) => update({ tenantId: e.target.value })}
            >
              {ALLOWED_TENANTS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          ) : (
            <span className="badge demo">{settings.tenantId}</span>
          )}
        </div>
      </div>

      <Async state={state} isEmpty={(r) => r.length === 0} empty="No agent runs recorded yet for this tenant.">
        {(runs) => {
          const current = sel ?? runs[0].id
          return (
            <div className="split">
              <div className="panel" style={{ padding: 0, maxHeight: 580, overflow: 'auto' }}>
                {runs.map((r) => (
                  <button key={r.id} className="list-btn" aria-current={current === r.id} onClick={() => setSel(r.id)}>
                    <span>{r.goal || r.query}</span>
                    <small>
                      {r.id} · {r.agentName ? `${r.agentName} · ` : ''}{r.status}
                    </small>
                  </button>
                ))}
              </div>
              <RunDetail id={current} />
            </div>
          )
        }}
      </Async>
    </div>
  )
}
