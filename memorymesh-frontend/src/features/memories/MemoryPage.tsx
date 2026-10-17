import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { useSettings, ALLOWED_TENANTS } from '../../app/SettingsContext'
import { Async, StatusBadge } from '../../components/StateViews'
import { DemoNote, PageHead } from '../../components/PageHead'
import { useAsync } from '../../lib/useAsync'
import type { MemoryKind, MemoryRecord } from '../../types'
import { layoutGraph } from '../graph/layout'
import { KIND_COLOR } from '../graph/GraphPage'

const TABS: { key: MemoryKind | 'all' | 'graph'; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'fact', label: 'Facts' },
  { key: 'decision', label: 'Decisions' },
  { key: 'task', label: 'Tasks' },
  { key: 'procedure', label: 'Procedures' },
  { key: 'episode', label: 'Episodes' },
  { key: 'graph', label: 'Graph' },
]

export default function MemoryPage() {
  const { api, settings, update } = useSettings()
  const [tab, setTab] = useState<MemoryKind | 'all' | 'graph'>('all')
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState<string | null>(null)

  const projects = useAsync(() => api.projects(settings.tenantId), `${api.mode}|${settings.baseUrl}|${settings.tenantId}`)

  // Fetch memory, tasks, and graph concurrently for the active project and tenant
  const state = useAsync(async () => {
    const [mem, taskList, graphData] = await Promise.all([
      api.memory(settings.projectId, settings.tenantId),
      api.tasks(settings.projectId, settings.tenantId).catch(() => []),
      api.graphOverview(settings.tenantId, 100).catch(() => ({ nodes: [], edges: [] })),
    ])

    // Convert enriched tasks from /api/projects/{p}/tasks into MemoryRecords if not already present
    const taskRecords: MemoryRecord[] = taskList.map((t) => ({
      id: t.id,
      kind: 'task' as MemoryKind,
      title: t.title,
      body: t.description || `Task status: ${t.status}${t.owner ? ` · Owner: ${t.owner}` : ''}${t.blockers.length ? ` · Blocked by: ${t.blockers.join(', ')}` : ''}`,
      createdAt: '',
      relatedIds: t.dependsOn,
      status: t.status,
      version: t.revision,
      blockers: t.blockers,
    }))

    // Merge: replace memory tasks with enriched tasks
    const otherRecords = mem.filter((m) => m.kind !== 'task')
    const allRecords = [...otherRecords, ...taskRecords]

    return { records: allRecords, graph: graphData }
  }, `${api.mode}|${settings.baseUrl}|${settings.tenantId}|${settings.projectId}`)

  const filtered = useMemo(() => {
    if (!state.data) return []
    const term = q.trim().toLowerCase()
    return state.data.records.filter(
      (r) => (tab === 'all' || r.kind === tab) && (!term || `${r.title} ${r.body} ${r.id} ${r.chosenOption ?? ''} ${r.rationale ?? ''}`.toLowerCase().includes(term)),
    )
  }, [state.data, tab, q])

  const current = state.data?.records.find((r) => r.id === selected) ?? filtered[0]
  const graphPositions = useMemo(() => (state.data?.graph ? layoutGraph(state.data.graph) : new Map()), [state.data])

  return (
    <div className="page">
      <PageHead title="Memory Explorer">
        Inspect facts, decisions, tasks, procedures, episodes and knowledge graph connections for the project.
      </PageHead>
      <DemoNote />

      {/* Scope Controls: Tenant and Project */}
      <div className="panel" style={{ padding: '12px 16px', marginBottom: 16 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <label htmlFor="mem-tenant-select" className="label mono muted" style={{ fontSize: '.75rem' }}>TENANT</label>
            {settings.mode === 'api' ? (
              <select
                id="mem-tenant-select"
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

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <label htmlFor="mem-project-select" className="label mono muted" style={{ fontSize: '.75rem' }}>PROJECT</label>
            {projects.data && projects.data.length > 0 ? (
              <select
                id="mem-project-select"
                className="input"
                style={{ padding: '4px 10px', fontSize: '.8125rem', width: 'auto' }}
                value={settings.projectId}
                onChange={(e) => update({ projectId: e.target.value })}
              >
                {projects.data.some((p) => p.id === settings.projectId) ? null : <option value={settings.projectId}>{settings.projectId}</option>}
                {projects.data.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            ) : (
              <input
                id="mem-project-select"
                className="input"
                style={{ padding: '4px 10px', fontSize: '.8125rem', width: 'auto' }}
                value={settings.projectId}
                onChange={(e) => update({ projectId: e.target.value.trim() })}
                placeholder="project id"
              />
            )}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'center', marginBottom: 14, justifyContent: 'space-between' }}>
        <div className="field" style={{ margin: 0, maxWidth: 380, flex: '1 1 280px' }}>
          <label htmlFor="mem-search" className="sr-only">Search memory</label>
          <input
            id="mem-search"
            type="search"
            className="input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search titles, facts, rationales, IDs…"
          />
        </div>

        <div className="chips" role="tablist" aria-label="Memory subview">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              className="chip"
              onClick={() => setTab(t.key)}
            >
              {t.label}
              {state.data && t.key !== 'graph'
                ? ` (${t.key === 'all' ? state.data.records.length : state.data.records.filter((r) => r.kind === t.key).length})`
                : ''}
            </button>
          ))}
        </div>
      </div>

      <Async state={state} isEmpty={(d) => d.records.length === 0 && d.graph.nodes.length === 0} empty="No memory records for this project yet.">
        {({ graph }) => {
          if (tab === 'graph') {
            return (
              <div className="panel" style={{ padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <h2 style={{ fontSize: '1rem', margin: 0 }}>Project Graph Overview ({graph.nodes.length} nodes, {graph.edges.length} edges)</h2>
                  <Link to="/app/graph" className="btn btn-sm">Full screen graph view &rarr;</Link>
                </div>
                {graph.nodes.length === 0 ? (
                  <div className="state">No graph nodes returned by the backend.</div>
                ) : (
                  <div className="graph-wrap" style={{ height: 420 }}>
                    <svg viewBox="0 0 900 560" role="group" aria-label="Knowledge graph subview">
                      {graph.edges.map((e, i) => {
                        const a = graphPositions.get(e.source), b = graphPositions.get(e.target)
                        if (!a || !b) return null
                        return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="rgba(180,200,220,.2)" strokeWidth={1} strokeDasharray={e.type === 'depends_on' ? '4 3' : undefined} />
                      })}
                      {graph.nodes.map((n) => {
                        const p = graphPositions.get(n.id)
                        if (!p) return null
                        return (
                          <g key={n.id} className="gnode">
                            <circle cx={p.x} cy={p.y} r={n.kind === 'episode' ? 7 : 9} fill={KIND_COLOR[n.kind] || '#efeae2'} />
                            <text x={p.x} y={p.y + 24} textAnchor="middle" fontSize="11" fill="#8d97a7">{n.id}</text>
                          </g>
                        )
                      })}
                    </svg>
                  </div>
                )}
              </div>
            )
          }

          if (filtered.length === 0) {
            return <div className="state">No records match your filter criteria.</div>
          }

          return (
            <div className="split">
              <div className="panel" style={{ padding: 0, maxHeight: 580, overflow: 'auto' }}>
                {filtered.map((r) => (
                  <button
                    key={r.id}
                    className="list-btn"
                    aria-current={current?.id === r.id}
                    onClick={() => setSelected(r.id)}
                  >
                    <span>{r.title}</span>
                    <small>
                      {r.kind} · {r.id}
                      {r.status ? ` · ${r.status}` : ''}
                      {typeof r.confidence === 'number' ? ` · ${Math.round(r.confidence * 100)}%` : ''}
                    </small>
                  </button>
                ))}
              </div>

              {current && (
                <article className="panel" aria-label="Record detail">
                  <div className="chips" style={{ marginBottom: 12 }}>
                    <span className="badge">{current.kind}</span>
                    <span className="badge mono">{current.id}</span>
                    {current.status && <StatusBadge status={current.status} />}
                    {typeof current.confidence === 'number' && (
                      <span className="badge mono">Confidence: {Math.round(current.confidence * 100)}%</span>
                    )}
                    {typeof current.version === 'number' && (
                      <span className="badge mono">Rev: {current.version}</span>
                    )}
                  </div>

                  <h2 style={{ textTransform: 'none', letterSpacing: 0, fontFamily: 'var(--font)', fontSize: '1.25rem', color: 'var(--text)', marginBottom: 8 }}>
                    {current.title}
                  </h2>

                  <p style={{ margin: '12px 0', fontSize: '.9375rem', lineHeight: 1.6 }}>{current.body}</p>

                  {/* Fact Specific Details */}
                  {current.kind === 'fact' && (
                    <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(255,255,255,.02)', borderRadius: 6 }}>
                      <div className="mono muted" style={{ fontSize: '.75rem' }}>PROVENANCE & VALIDITY</div>
                      {current.validFrom && <div style={{ fontSize: '.8125rem', marginTop: 4 }}>Valid from: <span className="mono muted">{current.validFrom}</span></div>}
                      {current.sourceEpisodeId && <div style={{ fontSize: '.8125rem', marginTop: 4 }}>Source Episode: <button className="pill" onClick={() => { setTab('all'); setSelected(current.sourceEpisodeId!) }}>{current.sourceEpisodeId}</button></div>}
                    </div>
                  )}

                  {/* Decision Specific Details */}
                  {current.kind === 'decision' && (current.chosenOption || current.rationale) && (
                    <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(255,255,255,.02)', borderRadius: 6 }}>
                      {current.chosenOption && <div style={{ fontSize: '.875rem', marginBottom: 6 }}><b>Chosen Option:</b> {current.chosenOption}</div>}
                      {current.rationale && <div className="muted" style={{ fontSize: '.8125rem' }}><b>Rationale:</b> {current.rationale}</div>}
                    </div>
                  )}

                  {/* Task Specific Details */}
                  {current.kind === 'task' && current.blockers && current.blockers.length > 0 && (
                    <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(229,130,111,.08)', border: '1px solid rgba(229,130,111,.3)', borderRadius: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#e5826f', fontSize: '.875rem' }}>
                        <AlertTriangle size={15} /> <b>Active Blockers ({current.blockers.length})</b>
                      </div>
                      <div className="chips" style={{ marginTop: 6 }}>
                        {current.blockers.map((b) => (
                          <button key={b} className="pill" onClick={() => { setTab('all'); setSelected(b) }}>{b}</button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Procedure Specific Steps */}
                  {current.kind === 'procedure' && (
                    <div style={{ marginTop: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <span className="mono muted" style={{ fontSize: '.75rem' }}>PROCEDURE STEPS</span>
                        {current.approved !== undefined && (
                          <span className={`badge ${current.approved ? 'ok' : 'demo'}`}>
                            {current.approved ? 'Approved' : 'Pending Approval'}
                          </span>
                        )}
                      </div>
                      {current.steps && current.steps.length > 0 ? (
                        <ol style={{ paddingLeft: 20, margin: '8px 0', fontSize: '.875rem', color: 'var(--text)' }}>
                          {current.steps.map((st, i) => <li key={i} style={{ marginBottom: 4 }}>{st}</li>)}
                        </ol>
                      ) : (
                        <p className="muted" style={{ fontSize: '.8125rem' }}>No steps formatted.</p>
                      )}
                    </div>
                  )}

                  {current.createdAt && (
                    <p className="muted mono" style={{ fontSize: '.75rem', marginTop: 14 }}>
                      Recorded: {current.createdAt.slice(0, 19).replace('T', ' ')}
                    </p>
                  )}

                  {current.relatedIds.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <div className="label muted mono" style={{ fontSize: '.6875rem', marginBottom: 6 }}>RELATED CONNECTIONS</div>
                      <div className="chips">
                        {current.relatedIds.map((id) => (
                          <button
                            key={id}
                            className="pill"
                            onClick={() => {
                              setTab('all')
                              setQ('')
                              setSelected(id)
                            }}
                          >
                            {id}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </article>
              )}
            </div>
          )
        }}
      </Async>
    </div>
  )
}
