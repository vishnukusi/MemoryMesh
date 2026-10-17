import { Fragment, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUpRight, Menu, X } from 'lucide-react'
import { useSettings } from '../app/SettingsContext'
import { AudioToggle } from '../components/AudioToggle'
import { LogoMark } from '../components/Logo'
import { MediaSlot } from '../components/MediaSlot'
import { HERO } from '../lib/media'
import { initScrollScenes } from '../motion/scroll-scenes'
import '../styles/landing.css'

const NAV = [
  { href: '#story', label: 'Story' },
  { href: '#agents', label: 'Agents' },
  { href: '#architecture', label: 'Architecture' },
  { href: '#outcomes', label: 'Outcomes' },
]

const HEADLINE = ['Your agents should not', 'have to start from zero.']

const MEMORY = [
  { name: 'Episodic', body: 'What happened: conversations, sessions and events, kept in order.' },
  { name: 'Semantic', body: 'What is true and what was decided: facts and decisions, with their context.' },
  { name: 'Procedural', body: 'How work gets done: tasks, blockers and procedures, with their dependencies.' },
]

const AGENTS = [
  { name: 'Memory Curator', does: 'Extracts and updates entities, facts, decisions and tasks from new context.', result: 'New context lands in the graph as candidate records.' },
  { name: 'Investigator', does: 'Retrieves relevant facts, decisions, tasks, blockers, procedures and episodes.', result: 'Relevant records come back with their ids.' },
  { name: 'Planner', does: 'Reasons over what was retrieved and the task dependencies, recommends next steps and coordinates handoffs.', result: 'Next steps respect what is still blocked.' },
  { name: 'Verifier', does: 'Checks the proposed answer against evidence and returns references to the graph nodes used.', result: 'The answer ships with references you can open.' },
]

const OUTCOMES = [
  ['Preserve decisions', 'What was decided, and why, stays findable after the chat that produced it is gone.'],
  ['Recover context', 'A new session or a new agent starts from the project record instead of a blank prompt.'],
  ['Surface blockers', 'Task dependencies are explicit, so a stalled step shows what it is waiting on.'],
  ['Share across agents', 'Specialists read and write the same memory rather than each re-deriving it.'],
  ['Trace the evidence', 'Answers point back to the facts, decisions and episodes they relied on.'],
  ['Continue the work', 'Handoffs persist, so the next agent picks up where the last one stopped.'],
] as const

export default function LandingPage() {
  const root = useRef<HTMLDivElement>(null)
  const { reducedMotion } = useSettings()
  const [menu, setMenu] = useState(false)

  useEffect(() => {
    const el = root.current
    return el ? initScrollScenes(el, reducedMotion) : undefined
  }, [reducedMotion])

  return (
    <div ref={root} className="landing" data-motion={reducedMotion ? 'off' : 'on'}>
      <a className="skip-link" href="#story">Skip to content</a>
      <div className="progress" aria-hidden="true"><i data-progress /></div>

      <header className="lp-header" data-header data-menu={menu ? 'open' : 'closed'}>
        <a href="#top" className="brand" onClick={() => setMenu(false)}><LogoMark /> MemoryMesh</a>
        <nav aria-label="Primary" id="lp-nav">
          <ul>
            {NAV.map((n) => <li key={n.href}><a href={n.href} onClick={() => setMenu(false)}>{n.label}</a></li>)}
          </ul>
        </nav>
        <div className="lp-actions">
          <AudioToggle />
          <Link to="/app/overview" className="btn btn-sm">Open the console <ArrowUpRight size={14} aria-hidden="true" /></Link>
          <button className="btn btn-sm lp-menu" aria-expanded={menu} aria-controls="lp-nav" aria-label={menu ? 'Close menu' : 'Open menu'} onClick={() => setMenu((m) => !m)}>
            {menu ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>
      </header>

      <main id="top">
        {/* A. Opening: cinematic split hero with clean 3D subject and real HTML typography */}
        <section className="hero" data-hero aria-labelledby="hero-title">
          <div className="hero-grid wrap">
            <div className="hero-copy">
              <p className="eyebrow" data-hero-fade>Persistent memory for AI project agents</p>
              <h1 id="hero-title">
                {HEADLINE.map((line) => (
                  <span className="hero-line" key={line}>
                    {line.split(' ').map((w, i) => (
                      <Fragment key={i}>
                        <span className="w"><span data-hero-word>{w}</span></span>{' '}
                      </Fragment>
                    ))}
                  </span>
                ))}
              </h1>
              <p className="lede" data-hero-fade>
                Persistent project memory. Coordinated agents. Evidence you can trace.
              </p>
              <div className="cta-row" data-hero-fade>
                <a href="#story" className="btn btn-primary">
                  Explore the system <ArrowDown size={15} aria-hidden="true" />
                </a>
                <Link to="/app/overview" className="btn">
                  Open the console <ArrowUpRight size={15} aria-hidden="true" />
                </Link>
              </div>
            </div>

            <div className="hero-visual" data-hero-media>
              <div className="hero-visual-frame">
                <img
                  src={HERO.src}
                  width={HERO.width}
                  height={HERO.height}
                  alt={HERO.alt}
                  fetchPriority="high"
                  decoding="async"
                />
              </div>
            </div>
          </div>
          <a href="#story" className="scroll-cue" data-hero-fade aria-label="Scroll to the story">
            <span>Scroll</span>
            <i aria-hidden="true" />
          </a>
        </section>

        {/* B. Fragments to persistent memory. Media slot: public/assets/video/memory-story.mp4 */}
        <section id="story" className="sec" aria-labelledby="story-title">
          <div className="wrap split-wide">
            <div data-stagger>
              <p className="eyebrow">01 · The problem</p>
              <h2 id="story-title">Context dies when the chat ends.</h2>
              <p className="body">Every new session, and every separate agent, starts with a blank page. People re-explain the project, decisions get re-argued, and a blocker noticed last week is forgotten today. MemoryMesh keeps that context in one place so work can build on it.</p>
            </div>
            <MediaSlot slot="story" caption="From separate sessions to one shared memory." clipReveal parallax />
          </div>
          <div className="wrap">
            <ul className="ruled" data-stagger aria-label="Kinds of memory">
              {MEMORY.map((m, i) => (
                <li key={m.name}><span className="num">{String(i + 1).padStart(2, '0')}</span><h3>{m.name} memory</h3><p>{m.body}</p></li>
              ))}
            </ul>
          </div>
        </section>

        {/* C. Specialist agents. Media slot: public/assets/video/agent-coordination.mp4 (scrubbed by scroll when present) */}
        <section id="agents" className="sec sec-agents" aria-labelledby="agents-title">
          <div className="wrap">
            <div className="sec-head" data-stagger>
              <p className="eyebrow">02 · Four specialists</p>
              <h2 id="agents-title">Specialists coordinate around shared memory.</h2>
              <p className="body">Each role has one job. They read and write the same project graph, so the answer you get is supported by retrieved memory, not just plausible text.</p>
            </div>
            <div className="agents-grid" data-scrub-trigger>
              <div className="agents-stage">
                <MediaSlot slot="agents" caption="Four specialists, one shared memory." scrub clipReveal />
              </div>
              <ol className="steps">
                {AGENTS.map((a, i) => (
                  <li key={a.name} data-agent-step>
                    <span className="num">{String(i + 1).padStart(2, '0')}</span>
                    <h3>{a.name}</h3>
                    <p>{a.does}</p>
                    <p className="result"><b>Result</b> {a.result}</p>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        {/* D. Evidence-linked graph. Media slot: public/assets/video/knowledge-graph.mp4 */}
        <section id="evidence" className="sec" aria-labelledby="evidence-title">
          <div className="wrap split-wide flip">
            <MediaSlot slot="graph" caption="An answer, linked back to its evidence." clipReveal parallax />
            <div data-stagger>
              <p className="eyebrow">03 · Evidence</p>
              <h2 id="evidence-title">Every answer points back to its source.</h2>
              <p className="body">The Verifier returns references to the graph nodes an answer used, so you can open the fact, the decision or the episode behind it.</p>
              <ol className="trail" aria-label="Example evidence trail (illustrative, from the demo project)">
                <li><span>Answer</span>We use idempotency keys on payment writes.</li>
                <li><span>Decision · d-1</span>Use idempotency keys on payment writes.</li>
                <li><span>Fact · f-3</span>Duplicate charges came from webhook retries.</li>
                <li><span>Episode · ep-3</span>Design review: idempotency.</li>
              </ol>
              <p className="note">Illustrative trail from the demo project, not live data.</p>
            </div>
          </div>
        </section>

        {/* E. Tasks and handoffs. Media slot: public/assets/video/task-handoff.mp4 */}
        <section id="handoffs" className="sec" aria-labelledby="handoffs-title">
          <div className="wrap split-wide">
            <div data-stagger>
              <p className="eyebrow">04 · Continuity</p>
              <h2 id="handoffs-title">Blocked work stays visible. Handoffs persist.</h2>
              <p className="body">Tasks record what they depend on. A task whose dependency is unfinished is shown as blocked and cannot be completed early; once the dependency is done it becomes available, but nothing runs on its own. Handoffs are stored, so the next agent starts from the recorded state.</p>
              <dl className="deps" aria-label="Example dependency (illustrative, from the demo project)">
                <div><dt>Run load rehearsal</dt><dd className="blocked">blocked</dd></div>
                <div><dt>waits on · Provision staging database</dt><dd className="progress-s">in progress</dd></div>
              </dl>
              <p className="note">Illustrative example from the demo project.</p>
            </div>
            <MediaSlot slot="tasks" caption="Dependencies and handoffs that persist." clipReveal parallax />
          </div>
        </section>

        {/* F. Architecture: static, semantic DOM. */}
        <section id="architecture" className="sec" aria-labelledby="arch-title">
          <div className="wrap">
            <div className="sec-head" data-stagger>
              <p className="eyebrow">05 · Architecture</p>
              <h2 id="arch-title">Local-first, end to end.</h2>
              <p className="body">The browser talks only to the FastAPI backend. Inference runs locally in Ollama; memory lives in a FalkorDB property graph.</p>
            </div>
            <ol className="arch" data-stagger aria-label="Request flow">
              <li><h3>Frontend</h3><p>This React console. Sends <code>tenant_id</code> with every call.</p></li>
              <li><h3>FastAPI</h3><p>Exposes the API and validates tenant scope.</p></li>
              <li><h3>Specialist agents</h3><p>Curator, Investigator, Planner and Verifier, orchestrated per request.</p></li>
              <li className="stores"><h3>Local services</h3>
                <p><b>Ollama</b> runs <code>qwen3:4b</code> for local inference.</p>
                <p><b>FalkorDB</b> stores episodic, semantic and procedural memory as a property graph.</p></li>
            </ol>
            <div className="split-lists" data-stagger>
              <div><h3>Working today</h3><ul>
                <li>Persistent memory in a FalkorDB graph</li>
                <li>Four specialist agent roles</li>
                <li>Evidence references on answers</li>
                <li>Task dependencies and persistent handoffs</li>
                <li>Tenant-scoped API</li></ul></div>
              <div><h3>Prototype and optional</h3><ul>
                <li>This console runs on labelled demo data until you point it at the backend</li>
                <li>The images, video and audio on this page were made separately and are not part of the runtime</li></ul></div>
            </div>
          </div>
        </section>

        {/* G. Outcomes and conversion */}
        <section id="outcomes" className="sec" aria-labelledby="outcomes-title">
          <div className="wrap">
            <div className="sec-head" data-stagger>
              <p className="eyebrow">06 · Outcomes</p>
              <h2 id="outcomes-title">What changes for the people and agents doing the work.</h2>
            </div>
            <ul className="ruled outcomes" data-stagger>
              {OUTCOMES.map(([t, d], i) => <li key={t}><span className="num">{String(i + 1).padStart(2, '0')}</span><h3>{t}</h3><p>{d}</p></li>)}
            </ul>
          </div>
        </section>

        <section className="final" aria-labelledby="final-title">
          <div className="wrap" data-stagger>
            <h2 id="final-title">Stop rebuilding context. Start building on it.</h2>
            <div className="cta-row">
              <Link to="/app/overview" className="btn btn-primary">Open the console <ArrowUpRight size={15} aria-hidden="true" /></Link>
              <a href="#architecture" className="btn">See the architecture</a>
            </div>
            <p className="note">The console starts in demo mode with sample data. Nothing is sent anywhere until you switch to API mode in Settings.</p>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="wrap">
          <span className="brand"><LogoMark /> MemoryMesh</span>
          <nav aria-label="Footer">
            <ul>
              {NAV.map((n) => <li key={n.href}><a href={n.href}>{n.label}</a></li>)}
              <li><Link to="/app/overview">Console</Link></li>
              <li><Link to="/app/settings">Settings</Link></li>
            </ul>
          </nav>
          <p>Built with React, TypeScript, Vite and GSAP. FastAPI, FalkorDB and Ollama power the backend. Prototype frontend; see LICENSES_AND_ATTRIBUTION.md for asset notes.</p>
        </div>
      </footer>
    </div>
  )
}
