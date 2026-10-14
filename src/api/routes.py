"""FastAPI routes for MemoryMesh.

All endpoints use validated Pydantic schemas and consistent error handling.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel

from src.config import settings
from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.schemas import (
    ChatRequest, ChatResponse, HealthResponse, new_id,
    TaskStatus, HandoffStatus, TaskUpdateRequest,
)
from src.services.orchestration import process_chat
from src.services.model_service import check_ollama_health
from src.memory.retrieve import retrieve_session_history, retrieve_project_memory
from src.memory.update import update_task_status
from src.security.auth import is_authorized_tenant, is_authorized_admin

logger = logging.getLogger(__name__)
router = APIRouter()


def _validate_tenant_or_raise(tenant_id: str, api_key: Optional[str] = None):
    authorized, reason = is_authorized_tenant(tenant_id, api_key)
    if not authorized:
        if not api_key and settings.AUTH_ENABLED:
            raise HTTPException(status_code=401, detail=reason)
        raise HTTPException(status_code=403, detail=reason)


def _validate_admin_or_raise(api_key: Optional[str] = None):
    authorized, reason = is_authorized_admin(api_key)
    if not authorized:
        if not api_key and settings.AUTH_ENABLED:
            raise HTTPException(status_code=401, detail=reason)
        raise HTTPException(status_code=403, detail=reason)


# ─── Administrative Tenant-Wide Memory ──────────────────────────

@router.get("/api/admin/memory/search")
async def admin_memory_search(
    query: str = Query(...),
    tenant_id: str = Query(...),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Explicit tenant-wide administrative memory search requiring Master Key authorization."""
    _validate_tenant_or_raise(tenant_id, api_key)
    _validate_admin_or_raise(api_key)
    repo = GraphRepository(tenant_id)
    facts = await asyncio.to_thread(repo.search_facts_admin, query)
    decisions = await asyncio.to_thread(repo.search_decisions_admin, query)
    procedures = await asyncio.to_thread(repo.search_procedures_admin, query)
    return {
        "tenant_id": tenant_id,
        "query": query,
        "facts": facts,
        "decisions": decisions,
        "procedures": procedures,
    }


# ─── Health ──────────────────────────────────────────────────────

@router.get("/health")
@router.get("/api/health")
async def health():
    """System health check."""
    db_ok = await asyncio.to_thread(check_connection)
    ollama = check_ollama_health()
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        falkordb="connected" if db_ok else "unavailable",
        ollama="connected" if ollama["available"] else "unavailable",
        model=f"{ollama['model']} ({'loaded' if ollama.get('model_loaded') else 'not loaded'})",
        tenants=settings.ALLOWED_TENANTS,
    )


# ─── Chat ────────────────────────────────────────────────────────

@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Process a chat message through the full agent pipeline."""
    _validate_tenant_or_raise(request.tenant_id, api_key)

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Verify FalkorDB is available
    db_ok = await asyncio.to_thread(check_connection)
    if not db_ok:
        raise HTTPException(
            status_code=503,
            detail="FalkorDB is not available. Start it with: docker run -p 6379:6379 falkordb/falkordb"
        )

    return await process_chat(request)


# ─── Projects ───────────────────────────────────────────────────

@router.get("/api/projects")
async def get_projects(tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """List all projects for a tenant."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    projects = await asyncio.to_thread(repo.get_all_projects)
    return {"projects": projects, "tenant_id": tenant_id}


@router.get("/api/projects/{project_id}/tasks")
async def get_project_tasks(project_id: str, tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get all tasks for a project with dependency info."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    project = await asyncio.to_thread(repo.get_project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    tasks = await asyncio.to_thread(repo.get_tasks_by_project, project_id)
    # Enrich with blocker info
    enriched = []
    for t in tasks:
        blockers = await asyncio.to_thread(repo.get_task_blockers, t.get("id", ""))
        t["blockers"] = blockers
        enriched.append(t)
    return {"tasks": enriched, "project_id": project_id}


@router.get("/api/projects/{project_id}/memory")
async def get_project_memory(project_id: str, tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get comprehensive project memory."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    project = await asyncio.to_thread(repo.get_project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    memory = await asyncio.to_thread(retrieve_project_memory, repo, project_id)
    return {"memory": memory, "project_id": project_id}


@router.get("/api/projects/{project_id}/decisions")
async def get_project_decisions(project_id: str, tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get all decisions for a project."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    project = await asyncio.to_thread(repo.get_project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    decisions = await asyncio.to_thread(repo.get_decisions_by_project, project_id)
    return {"decisions": decisions, "project_id": project_id}


# ─── Sessions ───────────────────────────────────────────────────

@router.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str, tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get conversation history for a session."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    episodes = await asyncio.to_thread(retrieve_session_history, repo, session_id)
    return {"episodes": episodes, "session_id": session_id}


# ─── Agent Runs ─────────────────────────────────────────────────

@router.get("/api/runs")
async def get_runs(tenant_id: str = Query(...), limit: int = Query(20, le=100), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get recent agent runs."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    runs = await asyncio.to_thread(repo.get_recent_runs, limit)
    return {"runs": runs}


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get a specific agent run."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    run = await asyncio.to_thread(repo.get_agent_run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


# ─── Handoffs ───────────────────────────────────────────────────

@router.get("/api/handoffs")
async def get_handoffs(tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get all handoffs."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    handoffs = await asyncio.to_thread(repo.get_handoffs)
    return {"handoffs": handoffs}


@router.post("/api/handoffs/{handoff_id}/claim")
async def claim_handoff(handoff_id: str, tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Claim a pending handoff."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    result = await asyncio.to_thread(repo.claim_handoff, handoff_id)
    if result is None:
        raise HTTPException(status_code=409, detail="Handoff is not in pending state")
    return result


@router.post("/api/handoffs/{handoff_id}/complete")
async def complete_handoff(handoff_id: str, tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Mark a handoff as completed."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    result = await asyncio.to_thread(repo.complete_handoff, handoff_id)
    if result is None:
        raise HTTPException(status_code=409, detail="Handoff is not in claimed state")
    return result


# ─── Task Updates ───────────────────────────────────────────────

@router.post("/api/tasks/{task_id}/status")
async def update_task(task_id: str, request: TaskUpdateRequest, api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Update a task's status with optimistic concurrency and lifecycle transition checks."""
    _validate_tenant_or_raise(request.tenant_id, api_key)
    repo = GraphRepository(request.tenant_id)

    task = await asyncio.to_thread(repo.get_task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Validate status against enum
    valid = [s.value for s in TaskStatus]
    if request.new_status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")

    result = await asyncio.to_thread(
        update_task_status,
        repo,
        task_id,
        request.new_status,
        task.get("project_id", ""),
        request.expected_revision,
    )
    if isinstance(result, dict) and "error" in result:
        status_code = 409 if result.get("conflict") else 400
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result


# ─── Graph Explorer ─────────────────────────────────────────────

@router.get("/api/graph/stats")
async def graph_stats(tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get graph statistics."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    nodes = await asyncio.to_thread(repo.count_nodes)
    rels = await asyncio.to_thread(repo.count_relationships)
    return {"nodes": nodes, "relationships": rels}


@router.get("/api/graph/overview")
async def graph_overview(tenant_id: str = Query(...), limit: int = Query(100, le=500), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get graph nodes and edges for visualization."""
    _validate_tenant_or_raise(tenant_id, api_key)
    repo = GraphRepository(tenant_id)
    data = await asyncio.to_thread(repo.get_graph_overview, limit)
    return {"graph": data}


# ─── Seed / Demo ────────────────────────────────────────────────

@router.post("/api/seed")
async def seed_demo(tenant_id: str = Query(...), api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Seed demonstration data for a tenant."""
    _validate_tenant_or_raise(tenant_id, api_key)
    from scripts.seed_demo import seed_tenant
    result = await asyncio.to_thread(seed_tenant, tenant_id)
    return {"status": "seeded", "tenant_id": tenant_id, "details": result}
