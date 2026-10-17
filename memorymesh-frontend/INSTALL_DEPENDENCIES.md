# Install and dependencies

## Prerequisites

- Node.js **20.19 or newer** (declared in `package.json` `engines`; Vite 8 requires it). Verified here on **Node 22.22.0** with **npm 10.9.4**.
- Any current browser. Nothing else: no database, no backend and no API keys are needed to run the frontend.

## Commands

```bash
cd memorymesh-frontend
npm ci                 # clean install from package-lock.json
npm run dev            # dev server, http://localhost:5173
npm run typecheck      # tsc -b --noEmit
npm run lint           # eslint .
npm test               # vitest run (7 tests)
npm run build          # tsc -b && vite build  ->  dist/
npm run preview        # serve dist/ locally
```

Regenerate the lockfile after changing dependencies: `rm -rf node_modules package-lock.json && npm install`.
Use `npm install` (not `npm ci`) when you intentionally change `package.json`.

## Runtime dependencies

| Package | Version | Purpose | Required |
|---|---|---|---|
| react, react-dom | ^19.3.0 | UI | Required |
| react-router-dom | ^7.18.4 | Routing (`/` and `/app/*`) | Required |
| gsap | ^3.15.0 | Scroll orchestration (ScrollTrigger) of real media and page content | Required |
| lucide-react | ^1.57.0 | Interface icons | Required |
| @fontsource-variable/sora | ^5.3.0 | Self-hosted UI font (no Google Fonts request) | Required |
| @fontsource-variable/jetbrains-mono | ^5.3.0 | Self-hosted monospace font | Required |

## Dev dependencies

| Package | Purpose |
|---|---|
| vite, @vitejs/plugin-react | Dev server and production build |
| typescript ~5.9, @types/react, @types/react-dom, @types/node | Types |
| eslint, @eslint/js, typescript-eslint, eslint-plugin-react-hooks, globals | Linting |
| vitest, jsdom, @testing-library/react, @testing-library/jest-dom | Tests |

## Deliberately not installed

- **three / @react-three/fiber / @react-three/drei**: the visuals are supplied media, not generated 3D. Add Three.js only if you later supply a real `.glb` model (`public/assets/models/memory-core.glb`).
- **Lenis or other smooth-scroll libraries**: native scrolling is used; it is more robust with ScrollTrigger.
- **Any ElevenLabs or Higgsfield SDK**: neither is called at runtime. They are only tools you may use separately to make the files.

## Environment

Copy `.env.example` to `.env.local` if you want to change defaults (`VITE_API_BASE_URL`, `VITE_DEFAULT_MODE`, `VITE_DEFAULT_TENANT_ID`). Everything prefixed `VITE_` is shipped to the browser, so never put a secret there.

## Troubleshooting

- **`npm ci` fails on engine/peer errors**: check `node -v` is 20.19+.
- **Blank page in production**: serve `dist/` with SPA fallback (all paths to `index.html`), otherwise `/app/...` reloads 404. `npm run preview` does this.
- **My video does not show**: the file must be served with a `video/*` content type at the exact path in `MEDIA_ASSET_MAP.md`. A host that answers missing files with `index.html` is detected as "absent" on purpose.
- **Console shows a CORS or network error in API mode**: see `INTEGRATION_GUIDE.md`.
