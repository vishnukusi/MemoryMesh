import { useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { useSettings, ALLOWED_TENANTS } from '../../app/SettingsContext'
import { Async, StatusBadge } from '../../components/StateViews'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { DemoNote, PageHead } from '../../components/PageHead'
import { useAsync } from '../../lib/useAsync'
import type { Handoff, HandoffStatus } from '../../types'

const GROUPS: { status: HandoffStatus; label: string; hint: string }[] = [
  { status: 'pending', label: 'Pending', hint: 'Waiting for an agent to pick up.' },
  { status: 'claimed', label: 'Claimed', hint: 'An agent has taken it on.' },
  { status: 'completed', label: 'Completed', hint: 'Finished and kept in memory.' },
]

export default function HandoffsPage() {
  const { api, settings, update } = useSettings()
  const state = useAsync(() => api.handoffs(settings.tenantId), `${api.mode}|${settings.baseUrl}|${settings.tenantId}`)
  const [pending, setPending] = useState<{ h: Handoff; action: 'claim' | 'complete' } | null>(null)
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null)

  async function confirm() {
    if (!pending) return
    const { h, action } = pending
    setPending(null)
    try {
      if (action === 'claim') {
        await api.claimHandoff(h.id, settings.tenantId)
      } else {
        await api.completeHandoff(h.id, settings.tenantId)
      }
      setToast({
        text: `${h.id} ${action === 'claim' ? 'claimed' : 'completed'}${api.mode === 'demo' ? ' (demo: browser memory only)' : ''}`,
      })
      state.reload()
    } catch (e) {
      setToast({
        text: `Action failed: ${e instanceof Error ? e.message : String(e)}`,
        error: true,
      })
    }
  }

  return (
    <div className="page">
      <PageHead title="Agent handoffs">
        Work passed between agents. Handoffs persist in the graph, so the next agent begins from recorded state rather than a fresh prompt.
      </PageHead>
      <DemoNote>Demo mode: claim and complete actions are simulated in browser memory. Nothing is written to a backend.</DemoNote>

      {/* Tenant Selector */}
      <div className="panel" style={{ padding: '10px 16px', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <label htmlFor="handoffs-tenant" className="label mono muted" style={{ fontSize: '.75rem' }}>TENANT</label>
          {settings.mode === 'api' ? (
            <select
              id="handoffs-tenant"
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

      <Async state={state} isEmpty={(h) => h.length === 0} empty="No handoffs recorded yet for this tenant.">
        {(handoffs) => (
          <div className="grid cols-3">
            {GROUPS.map((g) => {
              const items = handoffs.filter((h) => h.status === g.status)
              return (
                <section key={g.status} className="panel" aria-labelledby={`ho-${g.status}`}>
                  <h2 id={`ho-${g.status}`}>
                    <span>{g.label}</span> · <span className="badge mono">{items.length}</span>
                  </h2>
                  <p className="muted" style={{ fontSize: '.8125rem', marginBottom: 12 }}>{g.hint}</p>
                  {items.length === 0 && <p className="muted" style={{ fontSize: '.8125rem' }}>None</p>}
                  {items.map((h) => (
                    <article key={h.id} className="card" style={{ marginBottom: 12 }}>
                      <div className="chips">
                        <StatusBadge status={h.status} />
                        <span className="badge mono">{h.id}</span>
                      </div>
                      <div style={{ margin: '8px 0', fontSize: '.9375rem', lineHeight: 1.5, color: 'var(--text)' }}>
                        {h.summary}
                      </div>
                      <div className="meta">
                        <b>{h.fromAgent}</b> → <b>{h.toAgent}</b>
                        {h.taskId ? ` · task ${h.taskId}` : ''}
                      </div>
                      {h.createdAt && (
                        <div className="muted mono" style={{ fontSize: '.6875rem', marginTop: 4 }}>
                          Created: {h.createdAt.slice(0, 19).replace('T', ' ')}
                        </div>
                      )}
                      {h.claimedAt && (
                        <div className="muted mono" style={{ fontSize: '.6875rem' }}>
                          Claimed: {h.claimedAt.slice(0, 19).replace('T', ' ')}
                        </div>
                      )}
                      {h.completedAt && (
                        <div className="muted mono" style={{ fontSize: '.6875rem' }}>
                          Completed: {h.completedAt.slice(0, 19).replace('T', ' ')}
                        </div>
                      )}
                      <div style={{ marginTop: 10 }}>
                        {h.status === 'pending' && (
                          <button className="btn btn-sm btn-primary" onClick={() => setPending({ h, action: 'claim' })}>
                            Claim handoff
                          </button>
                        )}
                        {h.status === 'claimed' && (
                          <button className="btn btn-sm" onClick={() => setPending({ h, action: 'complete' })}>
                            Mark completed
                          </button>
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
        title={pending?.action === 'claim' ? 'Claim this handoff?' : 'Mark handoff complete?'}
        confirmLabel={pending?.action === 'claim' ? 'Claim' : 'Complete'}
        onConfirm={() => void confirm()}
        onCancel={() => setPending(null)}
      >
        {pending && (
          <p>
            <b>{pending.h.id}</b>: {pending.h.summary}
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
