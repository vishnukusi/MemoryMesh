import { useMemo, useState } from 'react'
import { ZoomIn, ZoomOut, RotateCcw } from 'lucide-react'
import { useSettings, ALLOWED_TENANTS } from '../../app/SettingsContext'
import { Async } from '../../components/StateViews'
import { DemoNote, PageHead } from '../../components/PageHead'
import { useAsync } from '../../lib/useAsync'
import type { GraphOverview, GraphStats, MemoryKind } from '../../types'
import { layoutGraph } from './layout'

export const KIND_COLOR: Record<MemoryKind, string> = {
  fact: '#efeae2',
  decision: '#7fe3f0',
  task: '#6f8fd0',
  procedure: '#38b2ac',
  episode: '#e3b866',
}

function GraphView({ graph, stats }: { graph: GraphOverview; stats?: GraphStats }) {
  const [sel, setSel] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })

  const pos = useMemo(() => layoutGraph(graph), [graph])
  const node = graph.nodes.find((n) => n.id === sel)
  const neighbours = node
    ? graph.edges
        .filter((e) => e.source === node.id || e.target === node.id)
        .map((e) => ({
          e,
          other: graph.nodes.find((n) => n.id === (e.source === node.id ? e.target : e.source)),
        }))
    : []
  const source = neighbours.find((x) => x.other?.kind === 'episode')?.other

  const handleZoomIn = () => setZoom((z) => Math.min(2.5, +(z + 0.25).toFixed(2)))
  const handleZoomOut = () => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))
  const handleReset = () => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
    setSel(null)
  }

  // Calculate viewBox based on zoom and pan
  const baseW = 900
  const baseH = 560
  const viewBoxW = baseW / zoom
  const viewBoxH = baseH / zoom
  const viewBoxX = (baseW - viewBoxW) / 2 + pan.x
  const viewBoxY = (baseH - viewBoxH) / 2 + pan.y

  return (
    <div className="grid" style={{ gap: 14 }}>
      {/* Stats Summary from GET /api/graph/stats */}
      {stats && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
          <span className="badge ok">Nodes: {stats.nodes}</span>
          <span className="badge">Relationships: {stats.edges}</span>
          {stats.byKind &&
            Object.entries(stats.byKind).map(([k, cnt]) => (
              <span key={k} className="badge mono" style={{ fontSize: '.6875rem' }}>
                <i style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: KIND_COLOR[k as MemoryKind] || '#aaa', marginRight: 5 }} />
                {k}: {cnt}
              </span>
            ))}
        </div>
      )}

      <div className="split" style={{ gridTemplateColumns: 'minmax(0,1fr) 320px' }}>
        <div className="graph-wrap" style={{ position: 'relative' }}>
          {/* Zoom & Reset Controls */}
          <div
            style={{
              position: 'absolute',
              top: 12,
              right: 12,
              display: 'flex',
              gap: 6,
              zIndex: 10,
              background: 'rgba(15,20,28,.85)',
              padding: 4,
              borderRadius: 6,
              border: '1px solid var(--line)',
            }}
            role="toolbar"
            aria-label="Graph zoom controls"
          >
            <button className="btn btn-sm" onClick={handleZoomIn} title="Zoom in" aria-label="Zoom in">
              <ZoomIn size={14} />
            </button>
            <button className="btn btn-sm" onClick={handleZoomOut} title="Zoom out" aria-label="Zoom out">
              <ZoomOut size={14} />
            </button>
            <button className="btn btn-sm" onClick={handleReset} title="Reset zoom and selection" aria-label="Reset zoom and selection">
              <RotateCcw size={14} /> {Math.round(zoom * 100)}%
            </button>
          </div>

          <svg
            viewBox={`${viewBoxX} ${viewBoxY} ${viewBoxW} ${viewBoxH}`}
            role="group"
            aria-label="Interactive FalkorDB Memory graph. Use Tab to move between nodes and Enter to select."
          >
            {graph.edges.map((e, i) => {
              const a = pos.get(e.source)
              const b = pos.get(e.target)
              if (!a || !b) return null
              const on = node && (e.source === node.id || e.target === node.id)
              return (
                <line
                  key={i}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={on ? '#7fe3f0' : 'rgba(180,200,220,.18)'}
                  strokeWidth={on ? 2 : 1}
                  strokeDasharray={e.type === 'depends_on' ? '4 3' : undefined}
                />
              )
            })}
            {graph.nodes.map((n) => {
              const p = pos.get(n.id)
              if (!p) return null
              const dim = node && node.id !== n.id && !neighbours.some((x) => x.other?.id === n.id)
              const isSelected = sel === n.id
              return (
                <g
                  key={n.id}
                  className="gnode"
                  role="button"
                  tabIndex={0}
                  aria-pressed={isSelected}
                  aria-label={`${n.kind}: ${n.label}`}
                  opacity={dim ? 0.25 : 1}
                  onClick={() => setSel(n.id)}
                  onKeyDown={(ev) => {
                    if (ev.key === 'Enter' || ev.key === ' ') {
                      ev.preventDefault()
                      setSel(n.id)
                    }
                  }}
                >
                  <circle className="ring" cx={p.x} cy={p.y} r={isSelected ? 18 : 14} fill="none" stroke={isSelected ? '#7fe3f0' : 'transparent'} strokeWidth={1.5} />
                  <circle cx={p.x} cy={p.y} r={n.kind === 'episode' ? 7 : 9} fill={KIND_COLOR[n.kind] || '#efeae2'} />
                  <text x={p.x} y={p.y + 24} textAnchor="middle" fontSize="11" fill={isSelected ? '#efeae2' : '#8d97a7'}>
                    {n.id}
                  </text>
                </g>
              )
            })}
          </svg>

          <div className="legend" aria-label="Legend">
            {(Object.keys(KIND_COLOR) as MemoryKind[]).map((k) => (
              <span key={k}>
                <i style={{ background: KIND_COLOR[k] }} />
                {k}
              </span>
            ))}
            <span>dashed = task dependency</span>
          </div>
        </div>

        <aside className="panel" aria-label="Entity inspector" aria-live="polite">
          <h2>Inspector</h2>
          {!node ? (
            <p className="muted">Select a node in the graph to inspect its properties, connections, and provenance.</p>
          ) : (
            <div className="grid" style={{ gap: 12 }}>
              <div>
                <span className="badge">{node.kind}</span> <span className="badge mono">{node.id}</span>
              </div>
              <p style={{ fontWeight: 500, color: 'var(--text)', margin: '4px 0' }}>{node.label}</p>
              {source && (
                <p className="muted" style={{ fontSize: '.875rem' }}>
                  Source episode:{' '}
                  <button className="pill" onClick={() => setSel(source.id)}>
                    {source.id}
                  </button>{' '}
                  {source.label}
                </p>
              )}
              <div>
                <div className="label muted mono" style={{ fontSize: '.6875rem', marginBottom: 6 }}>
                  CONNECTED TO ({neighbours.length})
                </div>
                {neighbours.length === 0 ? (
                  <p className="muted" style={{ fontSize: '.75rem' }}>No connected neighbors found in current view.</p>
                ) : (
                  <div className="chips">
                    {neighbours.map(
                      ({ e, other }) =>
                        other && (
                          <button
                            key={other.id + e.type}
                            className="pill"
                            title={e.type}
                            onClick={() => setSel(other.id)}
                          >
                            {other.id} ({e.type})
                          </button>
                        ),
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}

export default function GraphPage() {
  const { api, settings, update } = useSettings()

  const state = useAsync(async () => {
    const [graph, stats] = await Promise.all([
      api.graphOverview(settings.tenantId, 100),
      api.graphStats(settings.tenantId).catch(() => undefined),
    ])
    return { graph, stats }
  }, `${api.mode}|${settings.baseUrl}|${settings.tenantId}`)

  return (
    <div className="page">
      <PageHead title="Knowledge graph">
        Facts, decisions, tasks, procedures and source episodes as a connected graph. Select a node to trace where it came from.
      </PageHead>
      <DemoNote />

      {/* Tenant Selector */}
      <div className="panel" style={{ padding: '10px 16px', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <label htmlFor="graph-tenant" className="label mono muted" style={{ fontSize: '.75rem' }}>TENANT</label>
          {settings.mode === 'api' ? (
            <select
              id="graph-tenant"
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

      <Async state={state} isEmpty={(d) => d.graph.nodes.length === 0} empty="The graph is empty for this tenant.">
        {({ graph, stats }) => <GraphView graph={graph} stats={stats} />}
      </Async>
    </div>
  )
}
