# MemoryMesh frontend

A media-first, cinematic landing page plus a prototype console for **MemoryMesh**, a local-first persistent memory and coordination layer for AI project agents (FalkorDB property graph, Ollama running `qwen3:4b`, FastAPI backend, four specialist roles: Memory Curator, Investigator, Planner, Verifier).

This folder is standalone. It does not touch, and does not need, your existing MemoryMesh repository. Copy it in later using `INTEGRATION_GUIDE.md`.

## The one rule behind this build

The visuals are **real image and video files**, not code. There is no Three.js, no canvas, no procedural animation anywhere in the source. GSAP only reveals, crops, parallaxes and sequences the supplied media and ordinary page content, and all of it lives in `src/motion/scroll-scenes.ts`.

- The hero is your reference image, rendered as a plain `<img>`: `public/assets/images/hero-reference.webp` (a crop of your attached screenshot; the untouched original is in `assets-source/`).
- Four video slots are waiting for your files. Until you add them the page shows a neutral panel, never a broken icon. See `MEDIA_ASSET_MAP.md`.

## Quick start

```bash
npm ci          # exact versions from package-lock.json
npm run dev     # http://localhost:5173
```

Other commands: `npm run build`, `npm run preview`, `npm run typecheck`, `npm run lint`, `npm test`.
Requires Node 20.19+ (verified on Node 22.22.0, npm 10.9.4). Details in `INSTALL_DEPENDENCIES.md`.

## Routes

| Route | What it is |
|---|---|
| `/` | Scroll-driven landing page |
| `/app/overview` | Memory counts, task blockers, recent runs, handoff counts |
| `/app/chat` | Project chat with evidence pills and an agent trace |
| `/app/memories` | Searchable explorer: facts, decisions, tasks, procedures, episodes |
| `/app/graph` | Graph explorer with an entity inspector (keyboard accessible) |
| `/app/tasks` | Dependency-aware board: pending, in progress, blocked, completed |
| `/app/runs` | Specialist run traces and evidence |
| `/app/handoffs` | Pending, claimed, completed handoffs with confirmation dialogs |
| `/app/health` | FastAPI / FalkorDB / Ollama status (API mode only) |
| `/app/settings` | Demo or API mode, base URL, tenant, project, motion and sound |

## Demo mode vs API mode

The console starts in **demo mode**: deterministic sample data held in browser memory, labelled as demo on every screen. Nothing is sent anywhere, no health is faked, and no write is reported as successful against a backend. Switch to **API mode** in Settings (or via `VITE_DEFAULT_MODE=api`) to call the documented FastAPI endpoints with `tenant_id` on every request. The response shapes were not verifiable without your backend, so all mapping is isolated in `src/lib/api/normalize.ts`; see `INTEGRATION_GUIDE.md`.

## Structure

```text
public/assets/{images,video,audio,models}/   your media goes here
assets-source/                               untouched original of the hero reference
src/
  app/            router shell for the console, settings context
  components/     MediaSlot, AudioToggle, dialogs, state views
  features/       chat, memories, graph, tasks, runs, handoffs, health
  pages/          LandingPage, OverviewPage, SettingsPage
  motion/         scroll-scenes.ts, the only animation code
  lib/api/        Api interface, HTTP client, response normalisers
  lib/mock/       deterministic demo backend
  lib/media.ts    registry of media filenames
  styles/         global, landing and console CSS
```

## Accessibility and performance

Honors `prefers-reduced-motion` and an in-app switch (no scenes run; every section is simply visible). No scroll trapping: the agents section uses `position: sticky`, not pinning. Sound is off by default and the control only appears if an audio file exists. Non-hero media is lazy: nothing is requested until a slot is within 400px of the viewport, and only one video plays at a time.

## Known gaps

- Real videos, posters and audio are not included. They are yours to supply.
- Browser checks were run in headless Chromium only. See the final report for what was and was not checked.
