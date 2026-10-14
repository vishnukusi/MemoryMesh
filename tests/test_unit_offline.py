import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.memory.tenant_scope import validate_tenant, get_allowed_tenants
from src.schemas import (
    new_id,
    ProjectNode,
    PersonNode,
    EpisodeNode,
    FactNode,
    DecisionNode,
    TaskNode,
    ProcedureNode,
    HandoffNode,
    AgentRunNode,
    FactStatus,
    TaskStatus,
    HandoffStatus,
    ExtractionResult,
    ExtractedFact,
    ExtractedDecision,
    ExtractedTask,
    ExtractedProcedure,
    InvestigationResult,
    PlannerAction,
    VerificationResult,
    EvidenceRef,
    AgentTraceSummary,
    ChatRequest,
    ChatResponse,
)
from src.services.model_service import _extract_json
from src.db import queries as Q


# ─── Config & Tenant Scope Tests ─────────────────────────────────

def test_tenant_validation():
    assert validate_tenant("tenant_alpha") is True
    assert validate_tenant("tenant_beta") is True
    assert validate_tenant("tenant_gamma") is False
    assert validate_tenant("invalid_tenant") is False
    assert validate_tenant("") is False


def test_tenant_allowed_list():
    tenants = get_allowed_tenants()
    assert "tenant_alpha" in tenants
    assert "tenant_beta" in tenants
    assert len(tenants) == 2


def test_graph_name_resolution():
    name_alpha = settings.get_graph_name("tenant_alpha")
    name_beta = settings.get_graph_name("tenant_beta")
    assert name_alpha != name_beta
    assert "alpha" in name_alpha
    assert "beta" in name_beta


def test_unauthorized_tenant_raises():
    with pytest.raises(ValueError):
        settings.get_graph_name("malicious_tenant")


# ─── Schema Validation Tests ─────────────────────────────────────

def test_project_node_defaults():
    proj = ProjectNode(name="Test Project")
    assert proj.id is not None
    assert proj.name == "Test Project"
    assert proj.status == "active"
    assert proj.created_at.endswith("Z")
    assert proj.updated_at.endswith("Z")


def test_fact_node_statuses():
    f = FactNode(
        subject="Phoenix",
        predicate="target_date",
        value="Friday",
        confidence=0.9,
        status=FactStatus.CURRENT.value,
    )
    assert f.subject == "Phoenix"
    assert f.confidence == 0.9
    assert f.version == 1


def test_task_node_revision_tracking():
    task = TaskNode(
        title="Deploy API",
        status=TaskStatus.IN_PROGRESS.value,
        revision=1,
    )
    assert task.title == "Deploy API"
    assert task.revision == 1
    assert task.status == "in_progress"


def test_handoff_node():
    handoff = HandoffNode(
        from_agent="planner",
        to_agent="curator",
        context_summary="Context here",
    )
    assert handoff.status == HandoffStatus.PENDING.value
    assert handoff.from_agent == "planner"
    assert handoff.to_agent == "curator"


def test_extraction_result_parsing():
    raw_data = {
        "facts": [
            {"subject": "App", "predicate": "language", "value": "Python", "confidence": 0.95}
        ],
        "decisions": [
            {"title": "Language choice", "chosen_option": "Python", "rationale": "Productivity"}
        ],
        "tasks": [
            {"title": "Setup repository", "status": "pending", "description": "Initialize git"}
        ],
        "procedures": [
            {"title": "Release procedure", "description": "Steps to release", "steps": ["test", "build"]}
        ],
    }
    result = ExtractionResult.model_validate(raw_data)
    assert len(result.facts) == 1
    assert result.facts[0].subject == "App"
    assert len(result.decisions) == 1
    assert len(result.tasks) == 1
    assert len(result.procedures) == 1


def test_investigation_result_defaults():
    inv = InvestigationResult(
        summary="Summary of findings",
        confidence=0.85,
    )
    assert inv.summary == "Summary of findings"
    assert inv.relevant_facts == []
    assert inv.relevant_tasks == []


def test_planner_action_structure():
    action = PlannerAction(
        action_type="create_handoff",
        recommendation="Assign task to curator",
        handoff_to="curator",
        reasoning="Task needs data extraction",
    )
    assert action.action_type == "create_handoff"
    assert action.handoff_to == "curator"


def test_verification_result():
    ref = EvidenceRef(
        node_type="Fact",
        node_id="fact-123",
        summary="Phoenix target is Friday",
    )
    vr = VerificationResult(
        is_valid=True,
        final_answer="The project launches on Friday.",
        evidence_refs=[ref],
    )
    assert vr.is_valid is True
    assert len(vr.evidence_refs) == 1
    assert vr.evidence_refs[0].node_id == "fact-123"


# ─── Model Output Extraction Tests ──────────────────────────────

def test_extract_json_clean_block():
    text = '{"key": "value", "numbers": [1, 2, 3]}'
    parsed = _extract_json(text)
    assert parsed == {"key": "value", "numbers": [1, 2, 3]}


def test_extract_json_markdown_wrapped():
    text = """Here is the extracted information:
```json
{
  "status": "success",
  "count": 42
}
```
Hope this helps!"""
    parsed = _extract_json(text)
    assert parsed is not None
    assert parsed["status"] == "success"
    assert parsed["count"] == 42


def test_extract_json_unwrapped_markdown():
    text = """```
{"action": "investigate"}
```"""
    parsed = _extract_json(text)
    assert parsed == {"action": "investigate"}


def test_extract_json_list():
    text = '[{"id": 1}, {"id": 2}]'
    parsed = _extract_json(text)
    assert isinstance(parsed, list)
    assert len(parsed) == 2


def test_extract_json_invalid():
    text = "This is not json at all."
    parsed = _extract_json(text)
    assert parsed is None


# ─── Parameterized Cypher Queries Tests ─────────────────────────

def test_all_queries_are_parameterized():
    """Verify all predefined queries use parameters ($param) to prevent Cypher injection."""
    queries_to_check = [
        Q.CREATE_PROJECT,
        Q.CREATE_PERSON,
        Q.CREATE_EPISODE,
        Q.CREATE_FACT,
        Q.CREATE_DECISION,
        Q.CREATE_TASK,
        Q.CREATE_PROCEDURE,
        Q.CREATE_AGENT_RUN,
        Q.CREATE_HANDOFF,
        Q.UPDATE_TASK_STATUS,
        Q.SUPERSEDE_FACT,
        Q.CLAIM_HANDOFF,
        Q.COMPLETE_HANDOFF,
        Q.GET_EPISODES_BY_PROJECT,
        Q.GET_FACTS_BY_PROJECT,
        Q.GET_DECISIONS_BY_PROJECT,
        Q.GET_TASKS_BY_PROJECT,
        Q.GET_TASK_BLOCKERS,
    ]
    for q in queries_to_check:
        assert isinstance(q, str) and len(q.strip()) > 0
        assert "$" in q, f"Query appears unparameterized: {q[:40]}..."


def test_models_provide_all_create_query_parameters():
    """Verify each node model dictionary provides every parameter required by its CREATE query."""
    import re

    model_query_pairs = [
        (ProjectNode(name="P"), Q.CREATE_PROJECT),
        (PersonNode(name="P"), Q.CREATE_PERSON),
        (EpisodeNode(session_id="s", content="c"), Q.CREATE_EPISODE),
        (FactNode(subject="s", predicate="p", value="v"), Q.CREATE_FACT),
        (DecisionNode(title="t", chosen_option="o"), Q.CREATE_DECISION),
        (TaskNode(title="t"), Q.CREATE_TASK),
        (ProcedureNode(title="t"), Q.CREATE_PROCEDURE),
        (AgentRunNode(agent_name="a", goal="g"), Q.CREATE_AGENT_RUN),
        (HandoffNode(from_agent="a1", to_agent="a2"), Q.CREATE_HANDOFF),
    ]

    for model_instance, query_str in model_query_pairs:
        required_params = set(re.findall(r"\$([a-zA-Z0-9_]+)", query_str))
        model_keys = set(model_instance.model_dump().keys())
        missing = required_params - model_keys
        assert not missing, (
            f"{model_instance.__class__.__name__} is missing required query parameters: {missing}"
        )


# ─── Tenant Authentication & Authorization Tests ────────────────

from fastapi import HTTPException
from src.security.auth import is_authorized_tenant, verify_tenant_access
from src.domain.task_lifecycle import (
    validate_status_transition,
    validate_priority,
    detect_dependency_cycle,
    TaskLifecycleError,
    TaskDependencyCycleError,
)
from src.services.idempotency import (
    check_or_reserve_idempotency,
    finalize_idempotency_success,
    finalize_idempotency_failure,
)
from src.agents.curator import process_extraction
from src.agents.verifier import verify_and_respond


@pytest.mark.asyncio
async def test_auth_dev_mode_enabled(monkeypatch):
    monkeypatch.setattr(settings, "DEV_MODE", True)
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)

    # Valid tenant passes in dev mode without API key
    tenant = await verify_tenant_access("tenant_alpha", None)
    assert tenant == "tenant_alpha"

    # Unknown tenant fails even in dev mode
    with pytest.raises(HTTPException) as exc_info:
        await verify_tenant_access("unknown_tenant", None)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_api_key_enforcement(monkeypatch):
    monkeypatch.setattr(settings, "DEV_MODE", False)
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "MASTER_API_KEY", "master_secret_123")
    monkeypatch.setattr(settings, "TENANT_KEYS", {
        "tenant_alpha": "alpha_secret_456",
        "tenant_beta": "beta_secret_789",
    })

    # Missing API key -> 401
    with pytest.raises(HTTPException) as exc_info:
        await verify_tenant_access("tenant_alpha", None)
    assert exc_info.value.status_code == 401

    # Invalid API key -> 403
    with pytest.raises(HTTPException) as exc_info:
        await verify_tenant_access("tenant_alpha", "wrong_key")
    assert exc_info.value.status_code == 403

    # Valid tenant key for tenant_alpha -> succeeds
    tenant = await verify_tenant_access("tenant_alpha", "alpha_secret_456")
    assert tenant == "tenant_alpha"

    # Cross-tenant attack: key for tenant_beta accessing tenant_alpha -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        await verify_tenant_access("tenant_alpha", "beta_secret_789")
    assert exc_info.value.status_code == 403

    # Master key accessing tenant_alpha -> succeeds
    master_tenant = await verify_tenant_access("tenant_alpha", "master_secret_123")
    assert master_tenant == "tenant_alpha"


# ─── Task Lifecycle & Transition Tests ──────────────────────────

def test_task_lifecycle_valid_transitions():
    validate_status_transition("pending", "in_progress")
    validate_status_transition("in_progress", "completed")
    validate_status_transition("in_progress", "blocked")
    validate_status_transition("blocked", "in_progress")
    validate_status_transition("in_progress", "in_progress")


def test_task_lifecycle_invalid_transitions():
    # Blocked cannot jump straight to completed without in_progress or pending
    with pytest.raises(TaskLifecycleError):
        validate_status_transition("blocked", "completed")

    # Invalid status names rejected
    with pytest.raises(TaskLifecycleError):
        validate_status_transition("pending", "flying")


def test_task_lifecycle_active_blocker_rejection():
    # Cannot complete task if there are active unresolved blockers
    with pytest.raises(TaskLifecycleError) as exc_info:
        validate_status_transition(
            "in_progress", "completed",
            active_blockers=[{"id": "b1", "title": "blocker_task", "status": "in_progress"}],
        )
    assert "blocked by unresolved tasks" in str(exc_info.value)

    # Allowed when blockers are resolved (status=completed)
    validate_status_transition(
        "in_progress", "completed",
        active_blockers=[{"id": "b1", "title": "blocker_task", "status": "completed"}],
    )


def test_task_priority_validation():
    assert validate_priority("high") == "high"
    assert validate_priority("CRITICAL") == "critical"
    with pytest.raises(TaskLifecycleError):
        validate_priority("ultra_super_critical")


# ─── Dependency Cycle Detection Tests ───────────────────────────

def test_dependency_cycle_detection():
    # Direct self dependency raises TaskDependencyCycleError
    with pytest.raises(TaskDependencyCycleError):
        detect_dependency_cycle("A", "A", [])

    # 2-node cycle: A is blocked by B, now adding B is blocked by A
    existing = [("A", "B")]
    with pytest.raises(TaskDependencyCycleError):
        detect_dependency_cycle("B", "A", existing)

    # 3-node cycle: A is blocked by B, B is blocked by C; now adding C is blocked by A
    existing_3 = [("A", "B"), ("B", "C")]
    with pytest.raises(TaskDependencyCycleError):
        detect_dependency_cycle("C", "A", existing_3)

    # Valid DAG: A -> B, C -> B, adding D is blocked by C (no cycle, should not raise)
    existing_dag = [("A", "B"), ("C", "B")]
    detect_dependency_cycle("D", "C", existing_dag)


# ─── Idempotency Workflow Tests ─────────────────────────────────

from src.services.idempotency import (
    IdempotencyConcurrentError,
    IdempotencyConflictError,
)


def test_idempotency_lifecycle():
    class MockIdempRepo:
        def __init__(self):
            self.records = {}

        def get_idempotency_record(self, key):
            return self.records.get(key)

        def create_idempotency_record(self, key, tenant_id, project_id, payload_hash, status="running"):
            rec = {
                "key": key,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "payload_hash": payload_hash,
                "status": status,
                "response_json": "",
                "error": "",
            }
            self.records[key] = rec
            return rec

        def complete_idempotency_record(self, key, status, response_json="", error=""):
            if key in self.records:
                self.records[key]["status"] = status
                if response_json:
                    self.records[key]["response_json"] = response_json
                if error:
                    self.records[key]["error"] = error
            return self.records.get(key)

    repo = MockIdempRepo()
    req = ChatRequest(
        message="Plan sprint",
        tenant_id="tenant_alpha",
        project_id="proj_1",
        session_id="sess_1",
        idempotency_key="idem-key-123",
    )

    # 1. First reservation
    status, cached = check_or_reserve_idempotency(repo, req)
    assert status == "reserved"
    assert cached is None

    # 2. Concurrent invocation with same key raises IdempotencyConcurrentError
    with pytest.raises(IdempotencyConcurrentError):
        check_or_reserve_idempotency(repo, req)

    # 3. Finalize success
    resp = ChatResponse(
        answer="Sprint planned",
        session_id="sess_1",
        request_id="idem-key-123",
        status="success",
    )
    finalize_idempotency_success(repo, "idem-key-123", resp)

    # 4. Repeated invocation returns cached response
    status, cached_after = check_or_reserve_idempotency(repo, req)
    assert status == "completed"
    assert cached_after is not None
    assert cached_after.answer == "Sprint planned"

    # 5. Same key with conflicting message raises IdempotencyConflictError
    conflicting_req = ChatRequest(
        message="Completely different request",
        tenant_id="tenant_alpha",
        project_id="proj_1",
        session_id="sess_1",
        idempotency_key="idem-key-123",
    )
    with pytest.raises(IdempotencyConflictError):
        check_or_reserve_idempotency(repo, conflicting_req)


# ─── Project Scoping in Queries Tests ───────────────────────────

def test_queries_include_project_id_scoping():
    assert "$project_id" in Q.SEARCH_FACTS
    assert "$project_id" in Q.GET_CURRENT_FACTS
    assert "$project_id" in Q.SEARCH_DECISIONS
    assert "$project_id" in Q.GET_TASK_BY_TITLE
    assert "$project_id" in Q.SEARCH_PROCEDURES
    assert "$project_id" in Q.GET_PROJECT_DEPENDENCIES


# ─── Verifier Deterministic Validation Tests ────────────────────

@pytest.mark.asyncio
async def test_verifier_deterministic_evidence_filtering(monkeypatch):
    class MockVerifierRepo:
        def __init__(self):
            self.facts = {
                "fact_valid": {"id": "fact_valid", "project_id": "proj_1", "status": "current"},
                "fact_superseded": {"id": "fact_superseded", "project_id": "proj_1", "status": "superseded"},
                "fact_other_project": {"id": "fact_other_project", "project_id": "proj_2", "status": "current"},
            }

        def get_fact(self, fid):
            return self.facts.get(fid)

        def get_decision(self, did):
            return None

        def get_task(self, tid):
            return None

        def get_episode(self, eid):
            return None

    repo = MockVerifierRepo()
    # Mock LLM generation to return evidence citing all three facts + a non-existent fact
    from src.schemas import VerificationResult as VRSchema
    mock_llm_result = {
        "is_valid": True,
        "final_answer": "Verified launch details.",
        "evidence_refs": [
            {"node_type": "Fact", "node_id": "fact_valid", "summary": "Valid"},
            {"node_type": "Fact", "node_id": "fact_superseded", "summary": "Superseded"},
            {"node_type": "Fact", "node_id": "fact_other_project", "summary": "Other Proj"},
            {"node_type": "Fact", "node_id": "fact_nonexistent", "summary": "Ghost"},
        ],
        "warnings": [],
        "missing_evidence": [],
    }

    async def mock_generate_json(system_prompt, user_prompt):
        return mock_llm_result

    monkeypatch.setattr("src.agents.verifier.generate_json", mock_generate_json)

    res = await verify_and_respond(
        repo=repo,
        user_question="When is launch?",
        investigation=InvestigationResult(summary="Test"),
        plan=PlannerAction(recommendation="Test", action_type="none"),
        plan_result={"success": True},
        project_id="proj_1",
    )

    valid_ids = [ref.node_id for ref in res.evidence_refs]
    # Valid fact and superseded fact in proj_1 should be kept
    assert "fact_valid" in valid_ids
    assert "fact_superseded" in valid_ids
    # Non-existent and other project facts must be filtered out
    assert "fact_other_project" not in valid_ids
    assert "fact_nonexistent" not in valid_ids
    # Warnings should flag superseded and unverified facts
    warnings_str = " ".join(res.warnings)
    assert "fact_superseded" in warnings_str
    assert "fact_other_project" in warnings_str


# ─── Curator Fact Deduplication & Project Scoping Tests ─────────

@pytest.mark.asyncio
async def test_curator_duplicate_fact_prevention():
    class MockCuratorRepo:
        def __init__(self):
            self.facts = [
                {
                    "id": "existing-fact-1",
                    "subject": "Phoenix",
                    "predicate": "target_date",
                    "value": "Friday",
                    "status": "current",
                    "project_id": "proj_1",
                }
            ]
            self.created_facts = []
            self.superseded = []

        def search_facts(self, query, project_id=None, limit=10):
            res = []
            for f in self.facts:
                if project_id and f.get("project_id") != project_id:
                    continue
                if query.lower() in f.get("subject", "").lower():
                    res.append(f)
            return res

        def create_fact(self, fact, project_id, episode_id):
            d = fact.model_dump()
            self.created_facts.append(d)
            return d

        def supersede_fact(self, old_id, new_fact, project_id, episode_id):
            self.superseded.append((old_id, new_fact.id))
            return True

        def search_tasks(self, query, project_id=None, limit=10):
            return []

    repo = MockCuratorRepo()
    extraction = ExtractionResult(
        facts=[
            ExtractedFact(subject="Phoenix", predicate="target_date", value="Friday", confidence=0.9),
            ExtractedFact(subject="Phoenix", predicate="lead_engineer", value="Alice", confidence=0.85),
        ]
    )

    created = await process_extraction(
        repo=repo,
        extraction=extraction,
        project_id="proj_1",
        episode_id="ep_1",
    )

    # The duplicate fact ("Phoenix target_date Friday") should be skipped
    statuses = {item["value"]: item["status"] for item in created["facts"]}
    assert statuses["Friday"] == "duplicate_skipped"
    assert statuses["Alice"] == "created"
    assert len(repo.created_facts) == 1
    assert repo.created_facts[0]["value"] == "Alice"


# ─── API Routes & Security Tests ────────────────────────────────

from fastapi.testclient import TestClient
from src.api.main import app


def test_api_health_endpoint():
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "falkordb" in data
    assert "tenants" in data


def test_api_unauthorized_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(settings, "DEV_MODE", False)
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    client = TestClient(app)

    # Request without API key
    res = client.get("/api/projects", params={"tenant_id": "tenant_alpha"})
    assert res.status_code == 401


def test_api_cross_tenant_rejected_with_wrong_key(monkeypatch):
    monkeypatch.setattr(settings, "DEV_MODE", False)
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEY_HEADER", "X-API-Key")
    monkeypatch.setattr(settings, "TENANT_KEYS", {
        "tenant_alpha": "alpha-key-1",
        "tenant_beta": "beta-key-2",
    })
    client = TestClient(app)

    # Accessing tenant_alpha with tenant_beta's key
    res = client.get(
        "/api/projects",
        params={"tenant_id": "tenant_alpha"},
        headers={"X-API-Key": "beta-key-2"},
    )
    assert res.status_code == 403


def test_api_dev_mode_allowed_without_key(monkeypatch):
    monkeypatch.setattr(settings, "DEV_MODE", True)
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    client = TestClient(app)

    # In dev mode, invalid tenant still rejected with 403
    res_bad = client.get("/api/projects", params={"tenant_id": "hacker_tenant"})
    assert res_bad.status_code == 403


# ─── Production Config Security Tests ───────────────────────────

def test_production_config_rejection(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    # 1. Reject if DEV_MODE is True
    monkeypatch.setattr(settings, "DEV_MODE", True)
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    with pytest.raises(RuntimeError) as exc:
        settings.validate_production_config()
    assert "DEV_MODE cannot be enabled in production" in str(exc.value)

    # 2. Reject if AUTH_ENABLED is False
    monkeypatch.setattr(settings, "DEV_MODE", False)
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    with pytest.raises(RuntimeError) as exc:
        settings.validate_production_config()
    assert "AUTH_ENABLED must be True in production" in str(exc.value)

    # 3. Reject if default dev keys are still used
    monkeypatch.setattr(settings, "DEV_MODE", False)
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "TENANT_KEYS", {
        "tenant_alpha": "dev-alpha-key",
        "tenant_beta": "prod-secret-999",
    })
    with pytest.raises(RuntimeError) as exc:
        settings.validate_production_config()
    assert "non-default API key" in str(exc.value)

    # 4. Succeed when configured properly for production
    monkeypatch.setattr(settings, "TENANT_KEYS", {
        "tenant_alpha": "prod-secret-alpha-12345",
        "tenant_beta": "prod-secret-beta-67890",
    })
    monkeypatch.setattr(settings, "CORS_ALLOWED_ORIGINS", ["https://app.memorymesh.internal"])
    # Should not raise
    settings.validate_production_config()


# ─── Idempotency Abandoned Recovery Tests ───────────────────────

from datetime import datetime, timezone, timedelta


def test_idempotency_abandoned_recovery(monkeypatch):
    class MockTimeoutRepo:
        def __init__(self):
            self.records = {}

        def get_idempotency_record(self, key):
            return self.records.get(key)

        def create_idempotency_record(self, key, tenant_id, project_id, payload_hash, status="running"):
            rec = {
                "key": key,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "payload_hash": payload_hash,
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.records[key] = rec
            return rec

        def complete_idempotency_record(self, key, status, response_json="", error=""):
            if key in self.records:
                self.records[key]["status"] = status
                self.records[key]["updated_at"] = datetime.now(timezone.utc).isoformat()
            return self.records.get(key)

    repo = MockTimeoutRepo()
    req = ChatRequest(
        message="Process data",
        tenant_id="tenant_alpha",
        project_id="proj_1",
        session_id="sess_1",
        idempotency_key="stale-key-1",
    )

    # Set up an abandoned running reservation (created 300 seconds ago; timeout is 120s)
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    repo.records["stale-key-1"] = {
        "key": "stale-key-1",
        "tenant_id": "tenant_alpha",
        "project_id": "proj_1",
        "payload_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "status": "running",
        "updated_at": stale_time,
    }
    # Match request payload hash
    from src.services.idempotency import compute_payload_hash
    repo.records["stale-key-1"]["payload_hash"] = compute_payload_hash(req)

    # The stale reservation should be recovered and returned as reserved
    status, cached = check_or_reserve_idempotency(repo, req)
    assert status == "reserved"
    assert cached is None

    # Now with fresh running reservation (5 seconds ago), it must be rejected with IdempotencyConcurrentError
    repo.records["stale-key-1"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    with pytest.raises(IdempotencyConcurrentError):
        check_or_reserve_idempotency(repo, req)


# ─── Multi-Project Memory Isolation Tests ───────────────────────

def test_multi_project_memory_isolation():
    """Verify that queries for Project A never return items belonging to Project B."""
    class MockMultiProjectRepo:
        def __init__(self):
            self.facts = [
                {"id": "f_a", "subject": "Auth", "predicate": "provider", "value": "OAuth2", "project_id": "proj_A"},
                {"id": "f_b", "subject": "Auth", "predicate": "provider", "value": "SAML", "project_id": "proj_B"},
            ]
            self.decisions = [
                {"id": "d_a", "title": "DB Choice", "chosen_option": "PostgreSQL", "project_id": "proj_A"},
                {"id": "d_b", "title": "DB Choice", "chosen_option": "MongoDB", "project_id": "proj_B"},
            ]
            self.procedures = [
                {"id": "p_a", "title": "Deploy", "description": "Deploy to AWS", "project_id": "proj_A"},
                {"id": "p_b", "title": "Deploy", "description": "Deploy to GCP", "project_id": "proj_B"},
            ]

        def search_facts(self, query, project_id=None, limit=10):
            return [f for f in self.facts if (project_id is None or f.get("project_id") == project_id) and query.lower() in f["subject"].lower()]

        def search_decisions(self, query, project_id=None, limit=10):
            return [d for d in self.decisions if (project_id is None or d.get("project_id") == project_id) and query.lower() in d["title"].lower()]

        def search_procedures(self, query, project_id=None, limit=10):
            return [p for p in self.procedures if (project_id is None or p.get("project_id") == project_id) and query.lower() in p["title"].lower()]

    repo = MockMultiProjectRepo()

    # Search in Project A
    facts_a = repo.search_facts("Auth", project_id="proj_A")
    assert len(facts_a) == 1
    assert facts_a[0]["value"] == "OAuth2"

    decisions_a = repo.search_decisions("DB", project_id="proj_A")
    assert len(decisions_a) == 1
    assert decisions_a[0]["chosen_option"] == "PostgreSQL"

    procs_a = repo.search_procedures("Deploy", project_id="proj_A")
    assert len(procs_a) == 1
    assert procs_a[0]["description"] == "Deploy to AWS"

    # Search in Project B
    facts_b = repo.search_facts("Auth", project_id="proj_B")
    assert len(facts_b) == 1
    assert facts_b[0]["value"] == "SAML"

    decisions_b = repo.search_decisions("DB", project_id="proj_B")
    assert len(decisions_b) == 1
    assert decisions_b[0]["chosen_option"] == "MongoDB"

    procs_b = repo.search_procedures("Deploy", project_id="proj_B")
    assert len(procs_b) == 1
    assert procs_b[0]["description"] == "Deploy to GCP"


# ─── Optimistic Concurrency Conflict Tests ──────────────────────

def test_optimistic_concurrency_conflict():
    class MockConcurrencyRepo:
        def __init__(self):
            self.tasks = {
                "t1": {"id": "t1", "title": "Build UI", "status": "pending", "revision": 1, "project_id": "proj_1"}
            }

        def get_task(self, tid):
            return self.tasks.get(tid)

        def create_episode(self, episode):
            return episode.model_dump()

        def update_task_status(self, tid, new_status, expected_revision=None, enforce_lifecycle=True):
            t = self.tasks.get(tid)
            if not t:
                return None
            if expected_revision is not None and t.get("revision", 1) != expected_revision:
                return None  # Conflict: revision mismatch
            t["status"] = new_status
            t["revision"] = t.get("revision", 1) + 1
            return t

    repo = MockConcurrencyRepo()
    from src.memory.update import update_task_status as memory_update_task

    # First update using expected_revision=1 succeeds
    res1 = memory_update_task(repo, "t1", "in_progress", "proj_1", expected_revision=1)
    assert res1.get("status") == "in_progress"
    assert res1.get("revision") == 2

    # Second concurrent update using stale expected_revision=1 fails with conflict
    res2 = memory_update_task(repo, "t1", "completed", "proj_1", expected_revision=1)
    assert "error" in res2
    assert res2.get("conflict") is True


# ─── Orchestration Stage Failure & Terminal Run State Tests ─────

@pytest.mark.asyncio
async def test_orchestration_agent_failure_terminal_state(monkeypatch):
    class MockOrchestratorRepo:
        def __init__(self, tenant_id="tenant_alpha"):
            self.runs = {}
            self.episodes = {}
            self.idempotency_records = {}

        def create_episode(self, ep):
            self.episodes[ep.id] = ep.model_dump()
            return self.episodes[ep.id]

        def create_agent_run(self, run):
            self.runs[run.id] = {
                "id": run.id,
                "agent_name": run.agent_name,
                "status": "running",
            }
            return self.runs[run.id]

        def complete_agent_run(self, run_id, status, summary=None):
            if run_id in self.runs:
                self.runs[run_id]["status"] = status
                self.runs[run_id]["summary"] = summary

        def get_tasks_by_project(self, pid):
            return []

        def get_project(self, pid):
            return {"id": pid, "name": "Test Project"}

        def get_idempotency_record(self, key):
            return None

        def create_idempotency_record(self, **kwargs):
            pass

        def complete_idempotency_record(self, **kwargs):
            pass

    mock_repo_instance = MockOrchestratorRepo()
    monkeypatch.setattr("src.services.orchestration.GraphRepository", lambda tenant: mock_repo_instance)
    monkeypatch.setattr("src.services.orchestration.sync_check_ollama", lambda: True)

    # Inject failure into Curator
    async def mock_fail_curator(*args, **kwargs):
        raise RuntimeError("Curator simulated failure")

    monkeypatch.setattr("src.services.orchestration.extract_from_message", mock_fail_curator)

    req = ChatRequest(
        message="Start project alpha",
        tenant_id="tenant_alpha",
        project_id="proj_1",
        session_id="sess_1",
    )
    from src.services.orchestration import process_chat
    resp = await process_chat(req)

    assert resp.status == "error"
    assert "Curator simulated failure" in resp.error
    # Verify that the curator agent run reached terminal status 'failed'
    runs = list(mock_repo_instance.runs.values())
    assert len(runs) == 1
    assert runs[0]["agent_name"] == "curator"
    assert runs[0]["status"] == "failed"
    assert "Curator failed" in runs[0]["summary"]




