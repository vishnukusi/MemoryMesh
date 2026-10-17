# Integrating into `Agentic_AI/memorymesh`

This frontend was built without access to your repository, so nothing here was tested against your real backend.

## 1. Copy it in without overwriting anything

Put the folder beside your backend and Streamlit app, as a new directory, for example:

```text
Agentic_AI/memorymesh/
  (your existing FastAPI, schemas, seed scripts, Streamlit UI ...)
  frontend/            <- this folder (memorymesh-frontend renamed)
```

It only creates files inside its own folder. Do not merge it into an existing `package.json`, `src/` or `public/`. Do not copy `node_modules` or `dist`. Run `npm ci` inside `frontend/`.

## 2. Point it at the backend

```bash
cp .env.example .env.local
# VITE_API_BASE_URL=http://localhost:8000
# VITE_DEFAULT_MODE=api        (optional; otherwise switch in /app/settings)
# VITE_DEFAULT_TENANT_ID=<a tenant your backend knows>
```

## 3. Enable CORS on FastAPI

The browser calls FastAPI directly from the Vite origin. Add this to your app (adjust origins for production):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

The browser never talks to FalkorDB or Ollama; only to FastAPI.

## 4. Endpoint contract the client calls

Every tenant-scoped call carries `tenant_id` (query string, or JSON body where noted).

| Purpose | Call |
|---|---|
| Health | `GET /health` |
| Chat | `POST /api/chat` body `message, session_id, project_id, tenant_id, idempotency_key` |
| Projects | `GET /api/projects?tenant_id=` |
| Tasks | `GET /api/projects/{project_id}/tasks?tenant_id=` |
| Memory | `GET /api/projects/{project_id}/memory?tenant_id=` |
| Decisions | `GET /api/projects/{project_id}/decisions?tenant_id=` |
| Session history | `GET /api/sessions/{session_id}/history?tenant_id=` |
| Runs | `GET /api/runs?tenant_id=&limit=` and `GET /api/runs/{run_id}?tenant_id=` |
| Handoffs | `GET /api/handoffs?tenant_id=`, `POST /api/handoffs/{id}/claim?tenant_id=`, `POST /api/handoffs/{id}/complete?tenant_id=` |
| Task status | `POST /api/tasks/{task_id}/status` body `new_status, tenant_id` |
| Graph | `GET /api/graph/stats?tenant_id=` and `GET /api/graph/overview?tenant_id=&limit=` |

`POST /api/seed` exists as a helper (`seedBackend` in `src/lib/api/http.ts`) but is deliberately not wired to any button.

Unit tests (`src/lib/api/http.test.ts`) check these paths, `tenant_id` on every scoped call, the task-status body and the error handling.

## 5. Needs your confirmation

These are the places most likely to differ from your real responses. **All of them are isolated in `src/lib/api/normalize.ts`**, so adjusting is a one-file change.

- **Field names.** The normalisers accept likely variants (for example `task_id` or `id`, `content` or `description`) because the exact JSON was not available. Verify each against a real response.
- **`/api/memory` shape.** Handled as either a flat list or an object keyed by type (`facts`, `decisions`, ...). Memory is read-only in this UI; no create/edit/delete endpoint is assumed.
- **Graph overview.** Expects `nodes` and `edges`/`relationships`. `graph/stats` is mapped loosely.
- **Health.** `falkordb` and `ollama` may be a string, boolean or object; anything unrecognised is shown as `down`, never as healthy.
- **Task blockers.** `blockers` or `blocked_by` on a task is used as-is; the demo derives them from `dependsOn`.

## 6. Tenant handling

`tenant_id` and `project_id` are chosen in `/app/settings` and stored in `localStorage` (non-secret preferences only). There is no sign-in. The tenant is a plain parameter that your backend validates; the UI does not imply any authentication.

## 7. Limitations

- Prototype console: no auth, no create/edit/delete memory UI, no pagination beyond the `limit` parameters above.
- A failed API call is shown as an error with a retry button; a write is never reported as successful unless the backend returned success.
- Production hosting needs SPA fallback (all paths to `index.html`) for `/app/...`.

## 8. Do not overwrite

Your FastAPI app, Python schemas, seed scripts, backend tests and Streamlit UI are untouched by this folder. The only backend change suggested is the CORS block in step 3.
