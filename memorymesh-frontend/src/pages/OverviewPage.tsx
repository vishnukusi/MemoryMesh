import { Link } from 'react-router-dom'
import { useSettings, ALLOWED_TENANTS } from '../app/SettingsContext'
import { Async, StatusBadge } from '../components/StateViews'
import { DemoNote, PageHead } from '../components/PageHead'
import { useAsync } from '../lib/useAsync'

export default function OverviewPage() {
  const { api, settings, update } = useSettings()
  const { tenantId: t, projectId: p } = settings
  const state = useAsync(
    () => Promise.all([api.memory(p, t), api.tasks(p, t), api.handoffs(t), api.runs(t, 5)]),
    `${api.mode}|${settings.baseUrl}|${t}|${p}`,
  )

  return (
    <div className="page">
      <PageHead title="Project overview">
        Where project memory stands: what is stored, what is blocked, and what the agents did recently.
      </PageHead>
      <DemoNote />

      {/* Tenant & Project Context Bar */}
      <div className="panel" style={{ padding: '10px 16px', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <label htmlFor="ov-tenant" className="label mono muted" style={{ fontSize: '.75rem' }}>TENANT</label>
            {settings.mode === 'api' ? (
              <select
                id="ov-tenant"
                className="input"
                style={{ padding: '4px 10px', fontSize: '.8125rem', width: 'auto' }}
                value={t}
                onChange={(e) => update({ tenantId: e.target.value })}
              >
                {ALLOWED_TENANTS.map((tenant) => <option key={tenant} value={tenant}>{tenant}</option>)}
              </select>
            ) : (
              <span className="badge demo">{t}</span>
            )}
          </div>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <label htmlFor="ov-project" className="label mono muted" style={{ fontSize: '.75rem' }}>PROJECT</label>
            {settings.mode === 'api' ? (
              <input
                id="ov-project"
                type="text"
                className="input mono"
                style={{ padding: '4px 10px', fontSize: '.8125rem', width: 140 }}
                value={p}
                onChange={(e) => update({ projectId: e.target.value })}
              />
            ) : (
              <span className="badge demo">{p}</span>
            )}
          </div>
        </div>
      </div>

      <Async state={state}>
        {([memory, tasks, handoffs, runs]) => {
          const count = (k: string) => memory.filter((m) => m.kind === k).length
          const blocked = tasks.filter((x) => x.status === 'blocked' || x.blockers.length > 0)
          return (
            <div className="grid" style={{ gap: 16 }}>
              <div className="grid cols-4">
                {(['fact', 'decision', 'procedure', 'episode'] as const).map((k) => (
                  <div className="panel stat" key={k}>
                    <b>{count(k)}</b>
                    <span>{k}s in memory</span>
                  </div>
                ))}
              </div>
              <div className="grid cols-2">
                <section className="panel" aria-labelledby="ov-blockers">
                  <h2 id="ov-blockers">Task blockers</h2>
                  {blocked.length === 0 ? (
                    <p className="muted">No blocked tasks for project {p}.</p>
                  ) : (
                    <ul className="rows">
                      {blocked.map((x) => {
                        const blockerText =
                          x.blockerDetails && x.blockerDetails.length > 0
                            ? x.blockerDetails.map((b) => b.title || b.id).join(', ')
                            : x.blockers.join(', ') || '—'

                        return (
                          <li key={x.id}>
                            <span className="title">
                              {x.title}
                              <small>{x.id} · waiting on {blockerText}</small>
                            </span>
                            <StatusBadge status={x.status} />
                          </li>
                        )
                      })}
                    </ul>
                  )}
                  <p style={{ marginTop: 14 }}><Link to="/app/tasks" className="muted">Open task board →</Link></p>
                </section>
                <section className="panel" aria-labelledby="ov-runs">
                  <h2 id="ov-runs">Recent agent runs</h2>
                  {runs.length === 0 ? <p className="muted">No runs recorded.</p> : (
                    <ul className="rows">
                      {runs.map((r) => (
                        <li key={r.id}>
                          <span className="title">
                            {r.goal || r.query}
                            <small>{r.id} · {r.agentName ? `${r.agentName} · ` : ''}{r.traces.length} steps</small>
                          </span>
                          <StatusBadge status={r.status} />
                        </li>
                      ))}
                    </ul>
                  )}
                  <p style={{ marginTop: 14 }}><Link to="/app/runs" className="muted">All runs →</Link></p>
                </section>
                <section className="panel" aria-labelledby="ov-handoffs">
                  <h2 id="ov-handoffs">Handoffs</h2>
                  <ul className="rows">
                    {(['pending', 'claimed', 'completed'] as const).map((s) => (
                      <li key={s}><span>{s}</span><b>{handoffs.filter((h) => h.status === s).length}</b></li>
                    ))}
                  </ul>
                  <p style={{ marginTop: 14 }}><Link to="/app/handoffs" className="muted">Manage handoffs →</Link></p>
                </section>
                <section className="panel" aria-labelledby="ov-services">
                  <h2 id="ov-services">Services & Diagnostics</h2>
                  <p className="muted">
                    {api.mode === 'demo'
                      ? 'Service status is not checked in demo mode. Toggle API mode in Settings to connect to live services.'
                      : 'Live backend connected via Vite proxy. Open the Health page to inspect FastAPI, FalkorDB and Ollama.'}
                  </p>
                  <p style={{ marginTop: 14 }}><Link to="/app/health" className="muted">System Health →</Link></p>
                </section>
              </div>
            </div>
          )
        }}
      </Async>
    </div>
  )
}
