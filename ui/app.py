"""MemoryMesh — Streamlit Dashboard

A polished, professional interface for the MemoryMesh AI project coordinator.
All data comes from the FastAPI backend API.
"""

import os
import streamlit as st
import httpx
import json
import time
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────

API_URL = "http://localhost:8000"
TENANTS = {"Tenant Alpha": "tenant_alpha", "Tenant Beta": "tenant_beta"}

# ─── Page Config ─────────────────────────────────────────────────

st.set_page_config(
    page_title="MemoryMesh",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ──────────────────────────────────────────────────

st.markdown("""
<style>
    /* Dark theme enhancements */
    .main .block-container { padding-top: 1rem; max-width: 1200px; }

    .stApp > header { background-color: transparent; }

    /* Card style */
    .mesh-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.5rem 0;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .mesh-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(15, 52, 96, 0.4);
    }

    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .status-completed { background: #0d7377; color: #e0f7fa; }
    .status-in_progress, .status-in-progress { background: #e65100; color: #fff3e0; }
    .status-blocked { background: #b71c1c; color: #ffebee; }
    .status-pending { background: #4a148c; color: #f3e5f5; }
    .status-claimed { background: #1565c0; color: #e3f2fd; }
    .status-failed { background: #880e4f; color: #fce4ec; }
    .status-current { background: #1b5e20; color: #e8f5e9; }
    .status-superseded { background: #616161; color: #e0e0e0; }

    /* Hero */
    .hero-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00d2ff, #3a7bd5, #00d2ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .hero-sub {
        font-size: 1rem;
        color: #8899aa;
        margin-top: -0.5rem;
    }

    /* Evidence ref */
    .evidence-ref {
        background: #1a2332;
        border-left: 3px solid #3a7bd5;
        padding: 0.5rem 0.8rem;
        margin: 0.3rem 0;
        border-radius: 0 6px 6px 0;
        font-size: 0.85rem;
    }

    /* Agent trace */
    .agent-trace {
        background: #1a1a2e;
        border: 1px solid #2a2a4e;
        border-radius: 8px;
        padding: 0.8rem;
        margin: 0.4rem 0;
    }

    /* Sidebar enhancements */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
    }

    /* Chat messages */
    .chat-user {
        background: linear-gradient(135deg, #1a365d, #2a4a7f);
        border-radius: 12px 12px 4px 12px;
        padding: 0.8rem 1rem;
        margin: 0.4rem 0;
    }
    .chat-assistant {
        background: linear-gradient(135deg, #1a2e1a, #2a4f2a);
        border-radius: 12px 12px 12px 4px;
        padding: 0.8rem 1rem;
        margin: 0.4rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ─── Helper Functions ────────────────────────────────────────────

def get_api_headers() -> dict:
    """Return headers with X-API-Key if set in session state or environment."""
    key = st.session_state.get("api_key", os.environ.get("MEMORYMESH_API_KEY", ""))
    return {"X-API-Key": key} if key else {}


def api_get(path: str, params: dict = None) -> dict:
    """Make a GET request to the API."""
    try:
        r = httpx.get(
            f"{API_URL}{path}",
            params=params,
            headers=get_api_headers(),
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("❌ Cannot connect to MemoryMesh API. Start it with: `uvicorn src.api.main:app --port 8000`")
        return {}
    except Exception as e:
        st.error(f"API Error: {e}")
        return {}


def api_post(path: str, json_data: dict = None, params: dict = None) -> dict:
    """Make a POST request to the API."""
    try:
        r = httpx.post(
            f"{API_URL}{path}",
            json=json_data,
            params=params,
            headers=get_api_headers(),
            timeout=120.0,
        )
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("❌ Cannot connect to MemoryMesh API.")
        return {}
    except Exception as e:
        st.error(f"API Error: {e}")
        return {}


def status_badge(status: str) -> str:
    """Render a colored status badge."""
    css_class = f"status-{status.replace(' ', '-').lower()}"
    return f'<span class="status-badge {css_class}">{status}</span>'


def get_tenant_id() -> str:
    """Get the current tenant ID from session state."""
    return TENANTS.get(st.session_state.get("tenant_name", "Tenant Alpha"), "tenant_alpha")


# ─── Sidebar ─────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<p class="hero-title">🧠 MemoryMesh</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">AI Project Coordination • Persistent Graph Memory</p>', unsafe_allow_html=True)
    st.divider()

    # Tenant selector
    st.markdown("### 🏢 Tenant")
    tenant_name = st.selectbox(
        "Select Tenant",
        list(TENANTS.keys()),
        key="tenant_name",
        label_visibility="collapsed",
    )
    tenant_id = get_tenant_id()

    # API Key for authentication
    st.text_input(
        "API Key",
        value=st.session_state.get("api_key", os.environ.get("MEMORYMESH_API_KEY", "")),
        type="password",
        key="api_key",
        help="API Key for tenant authentication (required when AUTH_ENABLED=True)",
    )

    st.divider()

    # Navigation
    st.markdown("### 📍 Navigation")
    page = st.radio(
        "Go to",
        ["💬 Chat", "🧩 Memory Explorer", "🔍 Agent Trace",
         "📋 Task Board", "🤝 Handoffs", "💚 System Health"],
        label_visibility="collapsed",
    )

    st.divider()

    # Session management
    st.markdown("### 📝 Session")
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"session-{int(time.time())}"

    st.text(f"ID: {st.session_state.session_id[:20]}...")
    if st.button("🔄 New Session", use_container_width=True):
        st.session_state.session_id = f"session-{int(time.time())}"
        st.session_state.chat_history = []
        st.rerun()

    st.divider()

    # Seed data
    st.markdown("### 🌱 Demo Data")
    if st.button("Seed Current Tenant", use_container_width=True):
        with st.spinner("Seeding..."):
            result = api_post("/api/seed", params={"tenant_id": tenant_id})
            if result:
                st.success("✅ Demo data seeded!")


# ─── Chat Page ───────────────────────────────────────────────────

if page == "💬 Chat":
    st.markdown("## 💬 Project Chat")
    st.caption("Ask questions about your project, update tasks, or request coordination.")

    # Get project for this tenant
    projects = api_get("/api/projects", {"tenant_id": tenant_id})
    project_list = projects.get("projects", [])

    if not project_list:
        st.info("No projects found. Click 'Seed Current Tenant' to add demo data.")
        project_id = "default"
    else:
        project_names = {p.get("name", "?"): p.get("id", "") for p in project_list}
        selected = st.selectbox("Project", list(project_names.keys()))
        project_id = project_names.get(selected, "")

    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display chat
    for msg in st.session_state.chat_history:
        role = msg["role"]
        with st.chat_message(role):
            st.markdown(msg["content"])
            if role == "assistant" and msg.get("evidence"):
                with st.expander("📎 Evidence References"):
                    for ref in msg["evidence"]:
                        st.markdown(
                            f'<div class="evidence-ref">'
                            f'<strong>{ref.get("node_type", "?")}</strong> '
                            f'<code>{ref.get("node_id", "?")[:16]}...</code><br>'
                            f'{ref.get("summary", "")}</div>',
                            unsafe_allow_html=True,
                        )
            if role == "assistant" and msg.get("traces"):
                with st.expander("🔍 Agent Execution Trace"):
                    for trace in msg["traces"]:
                        st.markdown(
                            f'<div class="agent-trace">'
                            f'<strong>{trace.get("agent_name", "?")}</strong> — '
                            f'{status_badge(trace.get("status", "?"))} '
                            f'({trace.get("duration_ms", "?")}ms)<br>'
                            f'<em>{trace.get("goal", "")}</em></div>',
                            unsafe_allow_html=True,
                        )

    # Input
    user_input = st.chat_input("Type a message about your project...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("🧠 Processing through agent pipeline..."):
                response = api_post("/api/chat", json_data={
                    "message": user_input,
                    "session_id": st.session_state.session_id,
                    "project_id": project_id,
                    "tenant_id": tenant_id,
                })

            if response:
                answer = response.get("answer", "No response received.")
                st.markdown(answer)

                evidence = response.get("evidence", [])
                traces = response.get("agent_traces", [])

                if evidence:
                    with st.expander("📎 Evidence References"):
                        for ref in evidence:
                            st.markdown(
                                f'<div class="evidence-ref">'
                                f'<strong>{ref.get("node_type", "?")}</strong> '
                                f'<code>{ref.get("node_id", "?")[:16]}...</code><br>'
                                f'{ref.get("summary", "")}</div>',
                                unsafe_allow_html=True,
                            )

                if traces:
                    with st.expander("🔍 Agent Execution Trace"):
                        for trace in traces:
                            st.markdown(
                                f'<div class="agent-trace">'
                                f'<strong>{trace.get("agent_name", "?")}</strong> — '
                                f'{status_badge(trace.get("status", "?"))} '
                                f'({trace.get("duration_ms", "?")}ms)<br>'
                                f'<em>{trace.get("goal", "")}</em></div>',
                                unsafe_allow_html=True,
                            )

                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": answer,
                    "evidence": evidence,
                    "traces": traces,
                })
            else:
                st.error("Failed to get a response. Check API and FalkorDB status.")


# ─── Memory Explorer ─────────────────────────────────────────────

elif page == "🧩 Memory Explorer":
    st.markdown("## 🧩 Memory Explorer")
    st.caption("Inspect stored graph records — all data from FalkorDB.")

    # Get project memory
    projects = api_get("/api/projects", {"tenant_id": tenant_id})
    project_list = projects.get("projects", [])

    if not project_list:
        st.info("No projects found. Seed demo data first.")
    else:
        project_names = {p.get("name", "?"): p.get("id", "") for p in project_list}
        selected = st.selectbox("Project", list(project_names.keys()), key="mem_proj")
        project_id = project_names.get(selected, "")

        memory = api_get(f"/api/projects/{project_id}/memory", {"tenant_id": tenant_id})
        mem = memory.get("memory", {})

        # Graph stats
        stats = api_get("/api/graph/stats", {"tenant_id": tenant_id})
        if stats:
            cols = st.columns(4)
            node_counts = {n["label"]: n["count"] for n in stats.get("nodes", [])}
            with cols[0]:
                st.metric("Facts", node_counts.get("Fact", 0))
            with cols[1]:
                st.metric("Tasks", node_counts.get("Task", 0))
            with cols[2]:
                st.metric("Decisions", node_counts.get("Decision", 0))
            with cols[3]:
                st.metric("Episodes", node_counts.get("Episode", 0))

        tab_facts, tab_decisions, tab_tasks, tab_procedures, tab_episodes, tab_graph = st.tabs(
            ["📊 Facts", "⚖️ Decisions", "✅ Tasks", "📋 Procedures", "📝 Episodes", "🕸️ Graph"]
        )

        with tab_facts:
            facts = mem.get("facts", [])
            if facts:
                for f in facts:
                    with st.container():
                        cols = st.columns([3, 1])
                        with cols[0]:
                            st.markdown(f"**{f.get('subject', '?')}** {f.get('predicate', '?')} → *{f.get('value', '?')}*")
                            st.caption(f"ID: `{f.get('id', '?')[:16]}...` | Confidence: {f.get('confidence', '?')} | Version: {f.get('version', 1)}")
                        with cols[1]:
                            st.markdown(status_badge(f.get("status", "?")), unsafe_allow_html=True)
                        st.divider()
            else:
                st.info("No facts stored yet.")

        with tab_decisions:
            decisions = mem.get("decisions", [])
            if decisions:
                for d in decisions:
                    st.markdown(
                        f'<div class="mesh-card">'
                        f'<strong>⚖️ {d.get("title", "?")}</strong><br>'
                        f'<strong>Chose:</strong> {d.get("chosen_option", "?")}<br>'
                        f'<strong>Rationale:</strong> {d.get("rationale", "N/A")}<br>'
                        f'<code>{d.get("id", "?")[:20]}...</code></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No decisions stored yet.")

        with tab_tasks:
            tasks_data = api_get(f"/api/projects/{project_id}/tasks", {"tenant_id": tenant_id})
            tasks = tasks_data.get("tasks", [])
            if tasks:
                for t in tasks:
                    cols = st.columns([3, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{t.get('title', '?')}**")
                        st.caption(t.get("description", ""))
                        blockers = t.get("blockers", [])
                        if blockers:
                            blocker_names = ", ".join(b.get("title", "?") for b in blockers)
                            st.warning(f"🚫 Blocked by: {blocker_names}")
                    with cols[1]:
                        st.markdown(status_badge(t.get("status", "?")), unsafe_allow_html=True)
                    with cols[2]:
                        st.caption(f"Rev: {t.get('revision', 1)}")
                    st.caption(f"ID: `{t.get('id', '?')[:16]}...`")
                    st.divider()
            else:
                st.info("No tasks stored yet.")

        with tab_procedures:
            procs = mem.get("procedures", [])
            if procs:
                for p in procs:
                    with st.expander(f"📋 {p.get('title', '?')} {'✅' if p.get('approved') else '⏳'}"):
                        st.markdown(p.get("description", ""))
                        try:
                            steps = json.loads(p.get("steps_json", "[]"))
                            for i, step in enumerate(steps, 1):
                                st.markdown(f"{i}. {step}")
                        except json.JSONDecodeError:
                            st.text(p.get("steps_json", ""))
                        st.caption(f"ID: `{p.get('id', '?')[:16]}...` | Version: {p.get('version', 1)}")
            else:
                st.info("No procedures stored yet.")

        with tab_episodes:
            episodes = mem.get("recent_episodes", [])
            if episodes:
                for e in episodes:
                    icon = "👤" if e.get("actor") == "user" else "🤖"
                    css = "chat-user" if e.get("actor") == "user" else "chat-assistant"
                    st.markdown(
                        f'<div class="{css}">'
                        f'{icon} <strong>{e.get("actor", "?")}</strong> '
                        f'<span style="color:#888">({e.get("timestamp", "?")[:19]})</span><br>'
                        f'{e.get("content", "?")[:300]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.caption(f"Session: `{e.get('session_id', '?')[:16]}...` | ID: `{e.get('id', '?')[:16]}...`")
            else:
                st.info("No episodes stored yet.")

        with tab_graph:
            st.markdown("### Graph Structure")
            rel_stats = stats.get("relationships", []) if stats else []
            if rel_stats:
                st.markdown("**Relationship Types:**")
                for r in rel_stats:
                    st.markdown(f"- `{r.get('type', '?')}`: {r.get('count', 0)} edges")

            overview = api_get("/api/graph/overview", {"tenant_id": tenant_id, "limit": 50})
            graph_data = overview.get("graph", [])
            if graph_data:
                st.markdown(f"**Showing {len(graph_data)} node-edge pairs:**")
                for entry in graph_data[:30]:
                    node = entry.get("node", {})
                    labels = entry.get("node_labels", ["?"])
                    target = entry.get("target", {})
                    target_labels = entry.get("target_labels", [])
                    rel = entry.get("relationship")

                    if target and rel:
                        rel_type = rel if isinstance(rel, str) else "→"
                        st.text(
                            f"[{','.join(labels)}] {node.get('name', node.get('title', node.get('id', '?')[:12]))} "
                            f"—{rel_type}→ "
                            f"[{','.join(target_labels)}] {target.get('name', target.get('title', target.get('id', '?')[:12]))}"
                        )
                    else:
                        st.text(f"[{','.join(labels)}] {node.get('name', node.get('title', node.get('id', '?')[:12]))}")


# ─── Agent Trace ─────────────────────────────────────────────────

elif page == "🔍 Agent Trace":
    st.markdown("## 🔍 Agent Trace")
    st.caption("Inspect each agent's execution — what it read, wrote, and decided.")

    runs_data = api_get("/api/runs", {"tenant_id": tenant_id, "limit": 30})
    runs = runs_data.get("runs", [])

    if not runs:
        st.info("No agent runs recorded yet. Send a chat message to trigger agent execution.")
    else:
        for run in runs:
            with st.expander(
                f"{'🟢' if run.get('status') == 'completed' else '🔴'} "
                f"{run.get('agent_name', '?').upper()} — {run.get('goal', '?')[:60]}"
            ):
                cols = st.columns(3)
                with cols[0]:
                    st.markdown(f"**Agent:** {run.get('agent_name', '?')}")
                    st.markdown(f"**Status:** {status_badge(run.get('status', '?'))}", unsafe_allow_html=True)
                with cols[1]:
                    st.markdown(f"**Started:** {run.get('started_at', '?')[:19]}")
                    st.markdown(f"**Completed:** {(run.get('completed_at') or '—')[:19]}")
                with cols[2]:
                    st.markdown(f"**ID:** `{run.get('id', '?')[:16]}...`")

                st.markdown(f"**Goal:** {run.get('goal', '?')}")
                if run.get("summary"):
                    st.markdown(f"**Summary:** {run.get('summary', '')}")
                if run.get("error"):
                    st.error(f"Error: {run.get('error', '')}")


# ─── Task Board ──────────────────────────────────────────────────

elif page == "📋 Task Board":
    st.markdown("## 📋 Task Board")
    st.caption("View and manage project tasks with dependencies.")

    projects = api_get("/api/projects", {"tenant_id": tenant_id})
    project_list = projects.get("projects", [])

    if not project_list:
        st.info("No projects found.")
    else:
        project_names = {p.get("name", "?"): p.get("id", "") for p in project_list}
        selected = st.selectbox("Project", list(project_names.keys()), key="task_proj")
        project_id = project_names.get(selected, "")

        tasks_data = api_get(f"/api/projects/{project_id}/tasks", {"tenant_id": tenant_id})
        tasks = tasks_data.get("tasks", [])

        if tasks:
            # Group by status
            by_status = {}
            for t in tasks:
                s = t.get("status", "unknown")
                by_status.setdefault(s, []).append(t)

            cols = st.columns(4)
            status_order = ["pending", "in_progress", "blocked", "completed"]
            status_emoji = {"pending": "⏳", "in_progress": "🔨", "blocked": "🚫", "completed": "✅"}

            for i, status in enumerate(status_order):
                with cols[i]:
                    st.markdown(f"### {status_emoji.get(status, '?')} {status.replace('_', ' ').title()}")
                    for t in by_status.get(status, []):
                        st.markdown(
                            f'<div class="mesh-card">'
                            f'<strong>{t.get("title", "?")}</strong><br>'
                            f'<span style="color:#888">{t.get("description", "")[:60]}</span><br>'
                            f'{status_badge(status)}</div>',
                            unsafe_allow_html=True,
                        )
                        blockers = t.get("blockers", [])
                        if blockers:
                            for b in blockers:
                                st.caption(f"🚫 Blocked by: {b.get('title', '?')}")

            # Task update form
            st.divider()
            st.markdown("### Update Task Status")
            task_titles = {t.get("title", "?"): t.get("id", "") for t in tasks}
            selected_task = st.selectbox("Task", list(task_titles.keys()), key="update_task")
            new_status = st.selectbox("New Status", ["pending", "in_progress", "blocked", "completed"], key="new_status")
            if st.button("Update Status"):
                result = api_post(
                    f"/api/tasks/{task_titles[selected_task]}/status",
                    json_data={"new_status": new_status, "tenant_id": tenant_id},
                )
                if result and "error" not in str(result):
                    st.success(f"✅ Task '{selected_task}' updated to {new_status}")
                    st.rerun()
                else:
                    st.error(f"Update failed: {result}")
        else:
            st.info("No tasks found.")


# ─── Handoffs ────────────────────────────────────────────────────

elif page == "🤝 Handoffs":
    st.markdown("## 🤝 Agent Handoffs")
    st.caption("Track inter-agent work coordination.")

    handoffs_data = api_get("/api/handoffs", {"tenant_id": tenant_id})
    handoffs = handoffs_data.get("handoffs", [])

    if not handoffs:
        st.info("No handoffs recorded yet.")
    else:
        for h in handoffs:
            with st.expander(
                f"{'🟡' if h.get('status') == 'pending' else '🟢' if h.get('status') == 'completed' else '🔵' if h.get('status') == 'claimed' else '🔴'} "
                f"{h.get('from_agent', '?')} → {h.get('to_agent', '?')}"
            ):
                cols = st.columns(2)
                with cols[0]:
                    st.markdown(f"**From:** {h.get('from_agent', '?')}")
                    st.markdown(f"**To:** {h.get('to_agent', '?')}")
                    st.markdown(f"**Status:** {status_badge(h.get('status', '?'))}", unsafe_allow_html=True)
                with cols[1]:
                    st.markdown(f"**Created:** {h.get('created_at', '?')[:19]}")
                    if h.get("claimed_at"):
                        st.markdown(f"**Claimed:** {h['claimed_at'][:19]}")
                    if h.get("completed_at"):
                        st.markdown(f"**Completed:** {h['completed_at'][:19]}")

                st.markdown(f"**Context:** {h.get('context_summary', 'N/A')}")
                st.caption(f"ID: `{h.get('id', '?')}` | Task: `{h.get('task_id', 'N/A')[:16]}...`")

                # Action buttons
                if h.get("status") == "pending":
                    if st.button(f"Claim", key=f"claim_{h.get('id')}"):
                        result = api_post(
                            f"/api/handoffs/{h['id']}/claim",
                            params={"tenant_id": tenant_id},
                        )
                        if result:
                            st.success("✅ Handoff claimed!")
                            st.rerun()
                elif h.get("status") == "claimed":
                    if st.button(f"Complete", key=f"complete_{h.get('id')}"):
                        result = api_post(
                            f"/api/handoffs/{h['id']}/complete",
                            params={"tenant_id": tenant_id},
                        )
                        if result:
                            st.success("✅ Handoff completed!")
                            st.rerun()


# ─── System Health ───────────────────────────────────────────────

elif page == "💚 System Health":
    st.markdown("## 💚 System Health")

    health = api_get("/health")

    if health:
        cols = st.columns(3)
        with cols[0]:
            db_status = health.get("falkordb", "unknown")
            st.markdown(
                f"### {'✅' if db_status == 'connected' else '❌'} FalkorDB\n"
                f"**Status:** {db_status}"
            )
            if db_status != "connected":
                st.error(
                    "FalkorDB is not running. Start it with:\n\n"
                    "```bash\ndocker run -d --name falkordb -p 6379:6379 falkordb/falkordb\n```"
                )
        with cols[1]:
            ollama_status = health.get("ollama", "unknown")
            st.markdown(
                f"### {'✅' if ollama_status == 'connected' else '❌'} Ollama\n"
                f"**Status:** {ollama_status}"
            )
            if ollama_status != "connected":
                st.error(
                    "Ollama is not running. Install from https://ollama.ai then:\n\n"
                    "```bash\nollama serve\nollama pull qwen3:4b\n```"
                )
        with cols[2]:
            st.markdown(
                f"### 🤖 Model\n"
                f"**{health.get('model', 'unknown')}**"
            )

        st.divider()
        st.markdown("### Registered Tenants")
        for t in health.get("tenants", []):
            st.markdown(f"- `{t}`")

        st.divider()
        st.markdown("### Setup Instructions")
        st.markdown("""
        1. **Start FalkorDB:** `docker run -d --name falkordb -p 6379:6379 falkordb/falkordb`
        2. **Install Ollama:** Download from https://ollama.ai
        3. **Start Ollama:** `ollama serve`
        4. **Pull model:** `ollama pull qwen3:4b`
        5. **Start API:** `cd memorymesh && uvicorn src.api.main:app --port 8000 --reload`
        6. **Start UI:** `cd memorymesh && streamlit run ui/app.py --server.port 8501`
        7. **Seed data:** Click "Seed Current Tenant" in the sidebar
        """)
    else:
        st.error("Cannot connect to the API server.")
