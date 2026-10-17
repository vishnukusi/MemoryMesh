import { useEffect, useState, type FormEvent } from 'react'
import { Plus, RefreshCw, Send } from 'lucide-react'
import { useSettings, ALLOWED_TENANTS } from '../../app/SettingsContext'
import { DemoNote, PageHead } from '../../components/PageHead'
import { useAsync } from '../../lib/useAsync'
import type { AgentTrace, ChatResponse, EvidenceRef } from '../../types'

interface Turn { id: string; user: string; reply?: ChatResponse; error?: string }

const SUGGESTIONS = ['What is blocking the cutover?', 'Why did we pick idempotency keys?', 'Summarise the incident retro']

export default function ChatPage() {
  const { api, settings, update, sessionId, newSession } = useSettings()
  const [turns, setTurns] = useState<Turn[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<string | null>(null)

  const projects = useAsync(() => api.projects(settings.tenantId), `${api.mode}|${settings.baseUrl}|${settings.tenantId}`)

  // Load existing session history on initial mount or when sessionId/project changes
  useEffect(() => {
    let active = true
    if (api.mode === 'api' && sessionId) {
      void api.sessionHistory(sessionId, settings.tenantId).then((history) => {
        if (!active || !history.length) return
        const loaded: Turn[] = []
        for (let i = 0; i < history.length; i += 2) {
          const userMsg = history[i]?.role === 'user' ? history[i].content : ''
          const assistantMsg = history[i + 1]?.role === 'assistant' ? history[i + 1].content : ''
          if (userMsg) {
            loaded.push({
              id: `hist-${i}`,
              user: userMsg,
              reply: assistantMsg
                ? {
                    answer: assistantMsg,
                    session_id: sessionId,
                    evidence: [],
                    agent_traces: [],
                    handoff_created: false,
                    status: 'success',
                  }
                : undefined,
            })
          }
        }
        if (loaded.length > 0) setTurns(loaded)
      }).catch(() => {
        /* history not available yet */
      })
    }
    return () => { active = false }
  }, [api, sessionId, settings.tenantId])

  const last = [...turns].reverse().find((t) => t.reply)?.reply
  const traces: AgentTrace[] = last?.agent_traces ?? []

  async function send(message: string) {
    if (!message.trim() || busy) return
    const id = crypto.randomUUID()
    setTurns((t) => [...t, { id, user: message }])
    setText('')
    setBusy(true)
    try {
      const reply = await api.chat({
        message,
        session_id: sessionId,
        project_id: settings.projectId,
        tenant_id: settings.tenantId,
        idempotency_key: id,
      })
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, reply } : x)))
    } catch (e) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: e instanceof Error ? e.message : String(e) } : x)))
    } finally {
      setBusy(false)
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void send(text)
  }

  const evidenceById = (e: EvidenceRef) => open === e.id

  const handleNewSession = () => {
    newSession()
    setTurns([])
    setOpen(null)
  }

  return (
    <div className="page">
      <PageHead title="Project chat">Ask about the project. Answers list the memory records they were grounded in.</PageHead>
      <DemoNote>Demo mode: replies are scripted for sample questions. No model is called and nothing is retrieved from a graph. Switch to Live API in Settings to query the FalkorDB graph memory.</DemoNote>

      {/* Scope Selectors: Tenant, Project, and Session Controls */}
      <div className="panel" style={{ padding: '12px 16px', marginBottom: 16 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
            <label htmlFor="chat-tenant-select" className="label mono muted" style={{ fontSize: '.75rem' }}>TENANT</label>
            {settings.mode === 'api' ? (
              <select
                id="chat-tenant-select"
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

            <label htmlFor="chat-project-select" className="label mono muted" style={{ fontSize: '.75rem', marginLeft: 8 }}>PROJECT</label>
            {projects.data && projects.data.length > 0 ? (
              <select
                id="chat-project-select"
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
                id="chat-project-select"
                className="input"
                style={{ padding: '4px 10px', fontSize: '.8125rem', width: 'auto' }}
                value={settings.projectId}
                onChange={(e) => update({ projectId: e.target.value.trim() })}
                placeholder="project id"
              />
            )}
          </div>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className="badge mono" title="Current session ID">{sessionId}</span>
            <button className="btn btn-sm" onClick={handleNewSession} title="Start fresh conversation">
              <Plus size={13} aria-hidden="true" /> New session
            </button>
          </div>
        </div>
      </div>

      <div className="chat">
        <section aria-label="Conversation">
          <div className="msgs" aria-live="polite">
            {turns.length === 0 && (
              <div className="state">
                <span>Try a sample question:</span>
                <div className="chips">
                  {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => void send(s)}>{s}</button>)}
                </div>
              </div>
            )}
            {turns.map((t) => (
              <div key={t.id} className="grid" style={{ gap: 10 }}>
                <div className="msg user"><div className="who">You</div>{t.user}</div>
                {!t.reply && !t.error && <div className="msg" role="status"><div className="who">Agents</div>Working through curator, investigator, planner, and verifier…</div>}
                {t.error && <div className="msg" role="alert" style={{ borderColor: 'rgba(229,130,111,.5)' }}><div className="who">Error</div>{t.error}</div>}
                {t.reply && (
                  <div className="msg">
                    <div className="who" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span>MemoryMesh {api.mode === 'demo' && <span className="badge demo">demo reply</span>}</span>
                      {typeof t.reply.confidence === 'number' && (
                        <span className="badge mono" style={{ fontSize: '.6875rem' }}>
                          {Math.round(t.reply.confidence * 100)}% confidence
                        </span>
                      )}
                    </div>
                    <p style={{ whiteSpace: 'pre-wrap' }}>{t.reply.answer}</p>
                    {t.reply.error && <p className="muted" role="alert">Backend reported: {t.reply.error}</p>}
                    {t.reply.evidence.length > 0 && (
                      <div style={{ marginTop: 12 }}>
                        <div className="label muted mono" style={{ fontSize: '.6875rem', marginBottom: 6 }}>
                          GROUNDED EVIDENCE ({t.reply.evidence.length})
                        </div>
                        <div className="chips">
                          {t.reply.evidence.map((e) => (
                            <button
                              key={e.id}
                              className="pill"
                              aria-expanded={evidenceById(e)}
                              onClick={() => setOpen(evidenceById(e) ? null : e.id)}
                            >
                              {e.nodeType ? `${e.nodeType}: ` : ''}{e.id}
                            </button>
                          ))}
                        </div>
                        {t.reply.evidence.filter(evidenceById).map((e) => (
                          <div key={e.id} className="panel" style={{ marginTop: 10, padding: '10px 14px', background: 'rgba(255,255,255,.02)' }}>
                            <div className="chips" style={{ marginBottom: 4 }}>
                              <span className="badge">{e.kind}</span>
                              <span className="badge mono">{e.id}</span>
                              {typeof e.confidence === 'number' && <span className="badge">{Math.round(e.confidence * 100)}%</span>}
                            </div>
                            <p style={{ margin: '4px 0', fontSize: '.875rem', color: 'var(--text)' }}><b>{e.title}</b></p>
                            {e.excerpt && <p className="muted" style={{ margin: '4px 0', fontSize: '.8125rem' }}>{e.excerpt}</p>}
                            {e.sourceId && <p className="muted mono" style={{ fontSize: '.6875rem', margin: 0 }}>Source episode: {e.sourceId}</p>}
                          </div>
                        ))}
                      </div>
                    )}
                    {t.reply.handoff_created && (
                      <p className="badge in_progress" style={{ marginTop: 10 }}>
                        Handoff created: {typeof t.reply.handoff_created === 'string' ? t.reply.handoff_created : 'Recorded in memory'}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          <form onSubmit={onSubmit} className="field">
            <label htmlFor="chat-input">Message</label>
            <textarea
              id="chat-input"
              className="input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void send(text) }}
              placeholder="Ask about decisions, blockers, or what happened…"
              rows={3}
            />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
              <div>
                <button className="btn btn-primary" disabled={busy || !text.trim()}>
                  {busy ? <RefreshCw size={15} className="spin" aria-hidden="true" /> : <Send size={15} aria-hidden="true" />}
                  {' '}{busy ? 'Processing…' : 'Send'}
                </button>
                <span className="muted" style={{ fontSize: '.75rem', marginLeft: 12 }}>Ctrl/⌘ + Enter to send</span>
              </div>
            </div>
          </form>
        </section>

        <aside className="panel" aria-label="Agent trace">
          <h2>Agent pipeline trace</h2>
          {traces.length === 0 ? (
            <p className="muted">Send a message to see which specialists (Curator, Investigator, Planner, Verifier) executed and what they produced.</p>
          ) : (
            <ol className="trace" style={{ margin: 0, padding: 0 }}>
              {traces.map((t, i) => (
                <li key={i}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <b style={{ color: 'var(--brand)' }}>{t.agent}</b>
                    {t.status && <span className={`badge ${t.status === 'success' || t.status === 'ok' ? 'ok' : 'demo'}`}>{t.status}</span>}
                  </div>
                  {t.action && <div className="mono muted" style={{ fontSize: '.75rem', marginTop: 2 }}>{t.action}</div>}
                  {t.summary && <div className="muted" style={{ marginTop: 4 }}>{t.summary}</div>}
                  {t.error && <div style={{ color: '#e5826f', fontSize: '.75rem', marginTop: 4 }}>Error: {t.error}</div>}
                  {t.recordsRead && t.recordsRead.length > 0 && (
                    <div className="muted mono" style={{ fontSize: '.6875rem', marginTop: 4 }}>
                      Read: {t.recordsRead.join(', ')}
                    </div>
                  )}
                  {t.recordsWritten && t.recordsWritten.length > 0 && (
                    <div className="muted mono" style={{ fontSize: '.6875rem', marginTop: 2 }}>
                      Wrote: {t.recordsWritten.join(', ')}
                    </div>
                  )}
                  {t.durationMs !== undefined && (
                    <span className="mono muted" style={{ fontSize: '.6875rem', display: 'block', marginTop: 4 }}>
                      {t.durationMs} ms
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>
    </div>
  )
}
