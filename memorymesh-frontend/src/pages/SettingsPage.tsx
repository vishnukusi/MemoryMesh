import { useSettings } from '../app/SettingsContext'
import { PageHead } from '../components/PageHead'
import { useAsync } from '../lib/useAsync'

export default function SettingsPage() {
  const { settings, update, api, reducedMotion } = useSettings()
  const projects = useAsync(() => api.projects(settings.tenantId), `${api.mode}|${settings.baseUrl}|${settings.tenantId}`)

  return (
    <div className="page">
      <PageHead title="Settings">Choose between demo data and a real backend, and set your motion and audio preferences. Stored in this browser only; no secrets are kept.</PageHead>
      <div className="grid cols-2">
        <section className="panel" aria-labelledby="set-conn">
          <h2 id="set-conn">Connection</h2>
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="label muted mono" style={{ fontSize: '.75rem', marginBottom: 8 }}>MODE</legend>
            <div className="chips">
              <button className="chip" aria-pressed={settings.mode === 'demo'} onClick={() => update({ mode: 'demo' })}>Demo data</button>
              <button className="chip" aria-pressed={settings.mode === 'api'} onClick={() => update({ mode: 'api' })}>Live API</button>
            </div>
          </fieldset>
          <p className="muted" style={{ margin: '12px 0', fontSize: '.875rem' }} role="status">
            {settings.mode === 'demo' ? 'Demo mode is on: the console shows labelled sample data and is not connected to any backend.' : `API mode is on: requests go to ${settings.baseUrl}. There is no authentication in this prototype; tenant_id is sent as a plain parameter.`}
          </p>
          <div className="field" style={{ marginBottom: 14 }}>
            <label htmlFor="set-url">Backend base URL</label>
            <input id="set-url" className="input" value={settings.baseUrl} onChange={(e) => update({ baseUrl: e.target.value })} inputMode="url" placeholder="empty for Vite dev proxy (/api -> localhost:8000)" />
            <small className="muted" style={{ display: 'block', marginTop: 4 }}>
              {settings.baseUrl ? `Direct calls to ${settings.baseUrl}` : 'Using local Vite dev proxy to http://localhost:8000 (recommended, zero CORS configuration required)'}
            </small>
          </div>
          <div className="field" style={{ marginBottom: 14 }}>
            <label htmlFor="set-tenant">Tenant ID</label>
            {settings.mode === 'api' ? (
              <select id="set-tenant" className="input" value={settings.tenantId} onChange={(e) => update({ tenantId: e.target.value })}>
                <option value="tenant_alpha">tenant_alpha</option>
                <option value="tenant_beta">tenant_beta</option>
              </select>
            ) : (
              <input id="set-tenant" className="input" value={settings.tenantId} onChange={(e) => update({ tenantId: e.target.value.trim() })} />
            )}
            <small className="muted" style={{ display: 'block', marginTop: 4 }}>Backend validated tenant scope.</small>
          </div>
          <div className="field">
            <label htmlFor="set-project">Project</label>
            {projects.data && projects.data.length > 0 ? (
              <select id="set-project" className="input" value={settings.projectId} onChange={(e) => update({ projectId: e.target.value })}>
                {projects.data.some((p) => p.id === settings.projectId) ? null : <option value={settings.projectId}>{settings.projectId}</option>}
                {projects.data.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            ) : (
              <input id="set-project" className="input" value={settings.projectId} onChange={(e) => update({ projectId: e.target.value.trim() })} />
            )}
            {projects.error && <small className="muted" role="alert">Could not list projects: {projects.error}. Enter a project id manually.</small>}
          </div>
        </section>
        <section className="panel" aria-labelledby="set-a11y">
          <h2 id="set-a11y">Motion and sound</h2>
          <div className="switch">
            <label htmlFor="set-motion">Reduce motion<small className="muted" style={{ display: 'block' }}>{reducedMotion && !settings.reduceMotion ? 'Your system already asks for reduced motion.' : 'Turns off scroll choreography and animation on the landing page.'}</small></label>
            <input id="set-motion" type="checkbox" checked={settings.reduceMotion} onChange={(e) => update({ reduceMotion: e.target.checked })} />
          </div>
          <p className="muted" style={{ fontSize: '.875rem', paddingTop: 14, borderTop: '1px solid var(--line)' }}>Sound is always off when you arrive and never autoplays. A sound button appears on the landing page only if audio files have been added to <span className="mono">public/assets/audio/</span>.</p>
        </section>
      </div>
    </div>
  )
}
