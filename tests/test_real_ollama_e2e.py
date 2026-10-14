"""Real Ollama End-to-End integration tests for MemoryMesh.

Executes real model inference through the configured local Ollama instance (qwen3:4b).
Verifies:
1. Complete normal chat request lifecycle.
2. Correct execution and status tracking across all 4 agent stages.
3. Safe extraction and fallback on malformed structured output.
4. Consistent terminal state and database persistence on inference failure.
5. Idempotent replay preventing duplicate side-effects.
"""

import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.db.connection import check_connection, get_graph
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.schemas import ChatRequest, ChatResponse, ProjectNode, new_id
from src.services.model_service import check_ollama_health, _extract_json, generate_text
from src.services.orchestration import process_chat
from src.agents.curator import extract_from_message
from src.agents.investigator import investigate
from src.agents.planner import plan_action
from src.agents.verifier import verify_and_respond

TENANT = "tenant_alpha"

# Skip only if live services are not reachable
ollama_status = check_ollama_health()
ollama_available = ollama_status["available"] and ollama_status["model_loaded"]

pytestmark = pytest.mark.skipif(
    not (check_connection() and ollama_available),
    reason=f"Live FalkorDB and warm Ollama model '{settings.OLLAMA_MODEL}' required for real e2e tests",
)


@pytest.fixture(autouse=True)
def setup_tenant_schema():
    bootstrap_schema(TENANT)


# ─── 1 & 2. Complete Chat Lifecycle & All 4 Agent Stages ─────────

@pytest.mark.asyncio
async def test_real_ollama_chat_complete_lifecycle():
    """Submit a real chat request to qwen3:4b and verify all 4 stages complete and persist to FalkorDB."""
    repo = GraphRepository(TENANT)
    pid = f"proj-real-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Real Ollama E2E Project")
    repo.create_project(project)

    idem_key = f"real-e2e-{new_id()}"
    req = ChatRequest(
        message="We decided to use Redis 8 for session caching and completed the schema migration.",
        session_id=f"sess-{new_id()[:8]}",
        project_id=pid,
        tenant_id=TENANT,
        idempotency_key=idem_key,
    )

    # Execute complete orchestration with real Ollama inference
    resp = await process_chat(req)

    # 1. Verify complete response structure
    assert resp.status == "success", f"Expected success but got error: {resp.error}"
    assert len(resp.answer.strip()) > 0
    assert resp.session_id == req.session_id

    # 2. Verify all 4 agent stages executed and reported completed
    agent_names = [t.agent_name for t in resp.agent_traces]
    assert any("Curator" in name for name in agent_names), f"Curator missing from traces: {agent_names}"
    assert any("Investigator" in name for name in agent_names), f"Investigator missing: {agent_names}"
    assert any("Planner" in name for name in agent_names), f"Planner missing: {agent_names}"
    assert any("Verifier" in name for name in agent_names), f"Verifier missing: {agent_names}"

    for trace in resp.agent_traces:
        assert trace.status == "completed", f"Agent {trace.agent_name} failed: status={trace.status}"
        assert trace.duration_ms > 0

    # 3. Direct database inspection: verify episode was persisted
    episodes = repo.get_episodes_by_session(req.session_id)
    assert len(episodes) >= 2  # user message episode + assistant response episode
    user_ep = episodes[0]
    assert "Redis 8" in user_ep["content"]
    assert user_ep["project_id"] == pid

    # 4. Direct database inspection: verify agent runs were persisted with terminal status
    recent_runs = repo.get_recent_runs(limit=10)
    assert len(recent_runs) >= 4
    for r in recent_runs[:4]:
        assert r["status"] == "completed"

    # 5. Direct database inspection: verify idempotency record completed
    idem_rec = repo.get_idempotency_record(idem_key)
    assert idem_rec is not None
    assert idem_rec["status"] == "completed"
    assert idem_rec["reservation_token"] == req.reservation_token


# ─── 3. Malformed Structured Output Handling ────────────────────

def test_real_extract_json_malformed_tolerance():
    """Verify JSON extractor safely handles preamble commentary, markdown tags, and broken text."""
    # A. JSON wrapped in conversational text and markdown
    text_with_preamble = """
    Sure, here is the extracted information you requested:
    ```json
    {
      "facts": [{"subject": "Redis", "predicate": "version", "value": "8.0", "confidence": 0.95}],
      "decisions": [],
      "tasks": []
    }
    ```
    I hope this helps your project!
    """
    res = _extract_json(text_with_preamble)
    assert res is not None
    assert "facts" in res
    assert res["facts"][0]["subject"] == "Redis"

    # B. Missing closing braces or broken JSON syntax returns None instead of raising
    broken_json = '```json\n{"facts": [{"subject": "Postgres", incomplete...\n'
    assert _extract_json(broken_json) is None

    # C. Empty or plain conversational string
    assert _extract_json("I could not find any structured data in that message.") is None
    assert _extract_json("") is None


# ─── 4. Inference Failure / Timeout Safe Handling ───────────────

@pytest.mark.asyncio
async def test_real_orchestration_inference_failure_terminal_state(monkeypatch):
    """Simulate an inference failure and verify request, agent-run, and idempotency states remain consistent."""
    repo = GraphRepository(TENANT)
    pid = f"proj-fail-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Failure Handling Project")
    repo.create_project(project)

    idem_key = f"real-fail-{new_id()}"
    req = ChatRequest(
        message="Simulate network failure during planning stage.",
        session_id=f"sess-fail-{new_id()[:8]}",
        project_id=pid,
        tenant_id=TENANT,
        idempotency_key=idem_key,
    )

    # Inject failure into Planner
    async def mock_crashing_planner(*args, **kwargs):
        raise RuntimeError("Simulated Ollama inference socket disconnect")

    monkeypatch.setattr("src.services.orchestration.plan_action", mock_crashing_planner)

    resp = await process_chat(req)

    # Overall response reports error gracefully without uncaught crash
    assert resp.status == "error"
    assert "Simulated Ollama inference socket disconnect" in resp.error

    # User message episode must still be preserved in database
    episodes = repo.get_episodes_by_session(req.session_id)
    assert len(episodes) >= 1
    assert "Simulate network failure" in episodes[0]["content"]

    # Idempotency record must be marked failed in database so caller can safely retry
    rec = repo.get_idempotency_record(idem_key)
    assert rec is not None
    assert rec["status"] == "failed"
    assert "Simulated Ollama inference socket disconnect" in rec["error"]


# ─── 5. Idempotent Replay (Zero Duplicate Side-Effects) ─────────

@pytest.mark.asyncio
async def test_real_ollama_idempotent_replay_no_duplicate_side_effects():
    """Verify that retrying a completed request returns the cached response with zero duplicate side effects."""
    repo = GraphRepository(TENANT)
    pid = f"proj-replay-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Replay Test Project")
    repo.create_project(project)

    idem_key = f"real-replay-{new_id()}"
    req = ChatRequest(
        message="Create a deployment checklist for the staging environment.",
        session_id=f"sess-replay-{new_id()[:8]}",
        project_id=pid,
        tenant_id=TENANT,
        idempotency_key=idem_key,
    )

    # First execution: runs through real Ollama pipeline
    resp1 = await process_chat(req)
    assert resp1.status == "success"

    # Count database entities after first run
    episodes_count_1 = len(repo.get_episodes_by_session(req.session_id))
    runs_count_1 = repo.graph.query("MATCH (r:AgentRun) RETURN count(r)").result_set[0][0]

    # Second execution with identical idempotency key
    req_retry = ChatRequest(
        message="Create a deployment checklist for the staging environment.",
        session_id=req.session_id,
        project_id=pid,
        tenant_id=TENANT,
        idempotency_key=idem_key,
    )
    resp2 = await process_chat(req_retry)

    # Verify response is exact replay
    assert resp2.status == "success"
    assert resp2.answer == resp1.answer
    assert resp2.request_id == resp1.request_id

    # Verify zero duplicate episodes created
    episodes_count_2 = len(repo.get_episodes_by_session(req.session_id))
    assert episodes_count_2 == episodes_count_1, "Duplicate episodes created on idempotent replay!"

    # Verify zero duplicate agent runs created
    runs_count_2 = repo.graph.query("MATCH (r:AgentRun) RETURN count(r)").result_set[0][0]
    assert runs_count_2 == runs_count_1, "Duplicate agent runs triggered on idempotent replay!"
