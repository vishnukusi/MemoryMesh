import { useState } from 'react'
import { AlertCircle, AlertTriangle } from 'lucide-react'
import { useSettings, ALLOWED_TENANTS } from '../../app/SettingsContext'
import { Async } from '../../components/StateViews'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { DemoNote, PageHead } from '../../components/PageHead'
import { useAsync } from '../../lib/useAsync'
import type { Task, TaskStatus } from '../../types'

const COLUMNS: { status: TaskStatus; label: string }[] = [
  { status: 'pending', label: 'Pending' },
  { status: 'in_progress', label: 'In progress' },
  { status: 'blocked', label: 'Blocked' },
  { status: 'completed', label: 'Completed' },
]

// Lifecycle moves allowed. "blocked" is enforced by dependency rules.
const MOVES: Partial<Record<TaskStatus, { to: TaskStatus; label: string }[]>> = {
  pending: [{ to: 'in_progress', label: 'Start' }],
  in_progress: [{ to: 'completed', label: 'Mark complete' }, { to: 'pending', label: 'Back to pending' }],
  completed: [{ to: 'in_progress', label: 'Reopen' }],
}

export default function TasksPage() {
  const { api, settings, update } = useSettings()
  const projects = useAsync(() => api.projects(settings.tenantId), `${api.mode}|${settings.baseUrl}|${settings.tenantId}`)
  const state = useAsync(
    () => api.tasks(settings.projectId, settings.tenantId),
    `${api.mode}|${settings.baseUrl}|${settings.tenantId}|${settings.projectId}`,
  )
  const [pending, setPending] = useState<{ task: Task; to: TaskStatus } | null>(null)
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null)

  async function confirm() {
    if (!pending) return
    const { task, to } = pending
    setPending(null)
    try {
      // Pass expected_revision for optimistic concurrency safety
      await api.setTaskStatus(task.id, to, settings.tenantId, task.revision)
      setToast({
        text: api.mode === 'demo' ? `${task.id} → ${to} (demo: browser memory only)` : `${task.id} updated to ${to}`,
      })
      state.reload()
    } catch (e) {
      // If mutation fails or backend rejects (e.g. 409 conflict or blocked), preserve previous UI state and show error
      setToast({
        text: `Update rejected: ${e instanceof Error ? e.message : String(e)}`,
        error: true,
      })
    }
  }

  return (
    <div className="page">
      <PageHead title="Task board">
        Tasks with dependency tracking. A task cannot be marked completed while its dependencies remain open.
      </PageHead>
      <DemoNote />

      {/* Scope Controls */}
      <div className="panel" style={{ padding: '12px 16px', marginBottom: 16 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <label htmlFor="tasks-tenant-select" className="label mono muted" style={{ fontSize: '.75rem' }}>TENANT</label>
            {settings.mode === 'api' ? (
              <select
                id="tasks-tenant-select"
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
            <label htmlFor="tasks-project-select" className="label mono muted" style={{ fontSize: '.75rem' }}>PROJECT</label>
            {projects.data && projects.data.length > 0 ? (
              <select
                id="tasks-project-select"
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
                id="tasks-project-select"
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

      <Async state={state} isEmpty={(t) => t.length === 0} empty="No tasks found for this project yet.">
        {(tasks) => (
          <div className="board">
            {COLUMNS.map((col) => {
              const items = tasks.filter((t) => t.status === col.status)
              return (
                <section key={col.status} className="panel col" aria-labelledby={`col-${col.status}`}>
                  <h2 id={`col-${col.status}`}>
                    <span>{col.label}</span>
                    <span className="badge mono">{items.length}</span>
                  </h2>
                  {items.length === 0 && <p className="muted" style={{ fontSize: '.8125rem' }}>No tasks in this column.</p>}
                  {items.map((t) => (
                    <article key={t.id} className="card">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                        <div style={{ fontWeight: 500, color: 'var(--text)' }}>{t.title}</div>
                        {t.priority && (
                          <span
                            className="badge mono"
                            style={{
                              fontSize: '.625rem',
                              textTransform: 'uppercase',
                              background: t.priority === 'high' || t.priority === 'critical' ? 'rgba(229,130,111,.2)' : 'rgba(255,255,255,.05)',
                              color: t.priority === 'high' || t.priority === 'critical' ? '#e5826f' : 'inherit',
                            }}
                          >
                            {t.priority}
                          </span>
                        )}
                      </div>

                      {t.description && (
                        <p style={{ margin: '6px 0', fontSize: '.8125rem', color: 'var(--text-muted)' }}>{t.description}</p>
                      )}

                      <div className="meta">
                        <span className="mono">{t.id}</span>
                        {t.revision !== undefined && <span className="mono"> · rev {t.revision}</span>}
                        {t.owner && <span> · {t.owner}</span>}
                      </div>

                      {t.dependsOn.length > 0 && (
                        <div className="chips" aria-label="Depends on" style={{ marginTop: 6 }}>
                          {t.dependsOn.map((d) => {
                            const open = t.blockers.includes(d)
                            return (
                              <span
                                key={d}
                                className={`dep ${open ? 'open' : 'done'}`}
                                title={open ? 'Dependency open (blocking)' : 'Dependency completed'}
                              >
                                {d} {open ? '· open' : '· done'}
                              </span>
                            )
                          })}
                        </div>
                      )}

                      {t.blockers.length > 0 && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, color: '#e5826f', fontSize: '.75rem' }}>
                          <AlertTriangle size={12} />
                          <span>Waiting on: {t.blockerDetails?.map((b) => `${b.id} (${b.title})`).join(', ') || t.blockers.join(', ')}</span>
                        </div>
                      )}

                      <div className="chips" style={{ marginTop: 8 }}>
                        {(MOVES[t.status] ?? []).map((m) => {
                          const locked = m.to === 'completed' && t.blockers.length > 0
                          return (
                            <button
                              key={m.to}
                              className="btn btn-sm"
                              disabled={locked}
                              title={locked ? `Cannot complete: blocked by ${t.blockers.join(', ')}` : undefined}
                              onClick={() => setPending({ task: t, to: m.to })}
                            >
                              {m.label}
                            </button>
                          )
                        })}
                        {t.status === 'blocked' && (
                          <span className="muted" style={{ fontSize: '.75rem' }}>
                            Unlocks when open dependencies complete.
                          </span>
                        )}
                      </div>
                    </article>
                  ))}
                </section>
              )
            })}
          </div>
        )}
      </Async>

      <ConfirmDialog
        open={!!pending}
        title="Confirm Task Status Transition"
        confirmLabel="Confirm"
        onConfirm={() => void confirm()}
        onCancel={() => setPending(null)}
      >
        {pending && (
          <p>
            Move <b>{pending.task.id}</b> “{pending.task.title}” to <b>{pending.to.replace('_', ' ')}</b>.
            {pending.task.revision !== undefined && ` (Revision ${pending.task.revision})`}
            {api.mode === 'demo' && ' (Demo mode: changes update browser memory only)'}
          </p>
        )}
      </ConfirmDialog>

      {toast && (
        <div className={`toast ${toast.error ? 'error' : ''}`} role={toast.error ? 'alert' : 'status'}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {toast.error && <AlertCircle size={16} />}
            <span>{toast.text}</span>
          </div>
          <button className="btn btn-sm" style={{ marginLeft: 12 }} onClick={() => setToast(null)}>
            Dismiss
          </button>
        </div>
      )}
    </div>
  )
}
