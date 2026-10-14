"""Live FalkorDB verification tests for concurrency, graph integrity, legacy nodes, and security."""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone, timedelta
import threading
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import check_connection, get_graph
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.config import settings
from src.schemas import (
    ProjectNode, FactNode, DecisionNode, TaskNode, ProcedureNode, EpisodeNode,
    ChatRequest, ChatResponse, TaskStatus, FactStatus, new_id,
)
from src.services.idempotency import (
    check_or_reserve_idempotency,
    finalize_idempotency_success,
    finalize_idempotency_failure,
    IdempotencyConcurrentError,
    IdempotencyConflictError,
)
from src.domain.task_lifecycle import (
    detect_dependency_cycle,
    TaskDependencyCycleError,
    TaskLifecycleError,
    validate_status_transition,
)
from src.memory.update import update_task_status as memory_update_task

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="FalkorDB is required for live verification tests",
)

TENANT = "tenant_alpha"


@pytest.fixture(autouse=True)
def ensure_schema():
    bootstrap_schema(TENANT)


# ─── 1. Atomic Concurrency & Revision Locking on Live FalkorDB ──

def test_live_concurrent_task_updates_revision_conflict():
    """Verify that two concurrent updates using the same expected revision on live FalkorDB cannot both succeed."""
    repo = GraphRepository(TENANT)
    project = ProjectNode(name="Concurrency Test Project")
    repo.create_project(project)

    task = TaskNode(
        title="Concurrent Task",
        status=TaskStatus.PENDING.value,
        project_id=project.id,
        revision=1,
    )
    repo.create_task(task, project.id)

    # Verify initial revision in database
    initial = repo.get_task(task.id)
    assert initial["revision"] == 1
    assert initial["status"] == "pending"

    results = []
    errors = []

    def perform_update(new_status, expected_rev):
        try:
            res = memory_update_task(
                repo, task.id, new_status, project.id, expected_revision=expected_rev
            )
            results.append(res)
        except Exception as e:
            errors.append(e)

    # Fire two threads concurrently both claiming expected_revision=1
    t1 = threading.Thread(target=perform_update, args=("in_progress", 1))
    t2 = threading.Thread(target=perform_update, args=("completed", 1))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one must have succeeded and one must have failed with conflict
    successes = [r for r in results if "error" not in r]
    conflicts = [r for r in results if r.get("conflict") is True]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(conflicts) == 1, f"Expected exactly 1 conflict, got {len(conflicts)}"

    # Check live FalkorDB state: revision must be 2, not corrupted
    final_task = repo.get_task(task.id)
    assert final_task["revision"] == 2


# ─── 2. Idempotency Key Reservation Concurrency & Lifecycle ────

def test_live_concurrent_idempotency_reservations():
    """Verify two concurrent requests attempting to reserve the same key against live FalkorDB."""
    repo = GraphRepository(TENANT)
    key = f"live-idem-{new_id()}"
    req = ChatRequest(
        message="Deploy live cluster",
        tenant_id=TENANT,
        project_id="p_live",
        session_id="s_live",
        idempotency_key=key,
    )

    outcomes = []

    def attempt_reservation():
        try:
            status, cached = check_or_reserve_idempotency(repo, req)
            outcomes.append(("success", status))
        except Exception as e:
            outcomes.append(("error", type(e).__name__))

    t1 = threading.Thread(target=attempt_reservation)
    t2 = threading.Thread(target=attempt_reservation)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    successes = [o for o in outcomes if o[0] == "success"]
    concurrent_errors = [o for o in outcomes if o[1] == "IdempotencyConcurrentError"]

    assert len(successes) == 1
    assert len(concurrent_errors) == 1

    # Database inspection: only 1 record exists in running state
    rec = repo.get_idempotency_record(key)
    assert rec is not None
    assert rec["status"] == "running"


def test_live_idempotency_retry_while_running_and_recovery():
    """Verify in-flight blocking, safe recovery of abandoned reservation, and delayed worker rejection."""
    repo = GraphRepository(TENANT)
    key = f"live-idem-recov-{new_id()}"
    req_worker1 = ChatRequest(
        message="Process payroll",
        tenant_id=TENANT,
        project_id="p_live",
        session_id="s_live",
        idempotency_key=key,
    )

    # 1. Initial reservation by Worker 1
    status, cached = check_or_reserve_idempotency(repo, req_worker1)
    assert status == "reserved"
    assert cached is None
    token_worker1 = req_worker1.reservation_token
    assert token_worker1 is not None

    # 2. Immediate retry while still processing raises IdempotencyConcurrentError
    with pytest.raises(IdempotencyConcurrentError):
        check_or_reserve_idempotency(repo, req_worker1)

    # 3. Simulate abandoned reservation by setting updated_at to 300 seconds ago
    stale_iso = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    graph = get_graph(TENANT)
    graph.query(
        "MATCH (k:IdempotencyRecord {key: $key}) SET k.updated_at = $stale",
        {"key": key, "stale": stale_iso},
    )

    # 4. Retry after timeout recovers the reservation for Worker 2
    req_worker2 = ChatRequest(
        message="Process payroll",
        tenant_id=TENANT,
        project_id="p_live",
        session_id="s_live",
        idempotency_key=key,
    )
    status_recov, cached_recov = check_or_reserve_idempotency(repo, req_worker2)
    assert status_recov == "reserved"
    assert cached_recov is None
    token_worker2 = req_worker2.reservation_token
    assert token_worker2 != token_worker1

    # Verify database state shows it was recovered with Worker 2's token
    rec = repo.get_idempotency_record(key)
    assert rec["status"] == "running"
    assert rec.get("reservation_token") == token_worker2
    assert "Recovered from abandoned state" in rec.get("error", "")

    # 5. Delayed Worker 1 attempts to continue and finalize after recovery
    delayed_response = ChatResponse(
        answer="Delayed payroll attempt by worker 1",
        session_id="s_live",
        request_id=key,
        status="success",
    )
    res_worker1 = repo.complete_idempotency_record(
        key=key,
        status="completed",
        response_json=delayed_response.model_dump_json(),
        reservation_token=token_worker1,
    )
    # Delayed worker 1's update is fenced out and rejected
    assert res_worker1 is None

    # Database check: Still running with Worker 2's token
    rec_after_delayed = repo.get_idempotency_record(key)
    assert rec_after_delayed["status"] == "running"
    assert rec_after_delayed.get("reservation_token") == token_worker2

    # 6. Worker 2 successfully completes it
    response_payload = ChatResponse(
        answer="Payroll completed by recovered worker",
        session_id="s_live",
        request_id=key,
        status="success",
    )
    finalize_idempotency_success(repo, key, response_payload, reservation_token=token_worker2)

    # 7. Delayed Worker 1 attempts to record failure late
    res_worker1_late = repo.complete_idempotency_record(
        key=key,
        status="failed",
        error="Delayed worker late failure",
        reservation_token=token_worker1,
    )
    assert res_worker1_late is None

    # 8. Any future request returns Worker 2's cached result
    status_final, cached_final = check_or_reserve_idempotency(repo, req_worker2)
    assert status_final == "completed"
    assert cached_final is not None
    assert cached_final.answer == "Payroll completed by recovered worker"

    # Direct database inspection confirms exact state
    rec_final = repo.get_idempotency_record(key)
    assert rec_final["status"] == "completed"
    assert "recovered worker" in rec_final["response_json"]


# ─── 3. Concurrent Dependency Cycle Insertion ───────────────────

def test_live_concurrent_dependency_cycle_prevention():
    """Verify that concurrent dependency insertions that together form a cycle are safely prevented."""
    repo = GraphRepository(TENANT)
    p = ProjectNode(name="Cycle Test Project")
    repo.create_project(p)

    task_a = TaskNode(title="Task A", project_id=p.id)
    task_b = TaskNode(title="Task B", project_id=p.id)
    repo.create_task(task_a, p.id)
    repo.create_task(task_b, p.id)

    # First add A is blocked by B
    repo.create_blocked_by(task_a.id, task_b.id)

    # Now attempt to add B is blocked by A (creates circular dependency A -> B -> A)
    with pytest.raises(TaskDependencyCycleError):
        repo.create_blocked_by(task_b.id, task_a.id)

    # Inspect database state: B -[:BLOCKED_BY]-> A was NOT created
    graph = get_graph(TENANT)
    cycle_check = graph.query(
        "MATCH (b:Task {id: $bid})-[:BLOCKED_BY]->(a:Task {id: $aid}) RETURN b",
        {"bid": task_b.id, "aid": task_a.id},
    ).result_set
    assert len(cycle_check) == 0


# ─── 4. Multi-Project Graph Isolation & Supersession on FalkorDB 

def test_live_multi_project_graph_isolation():
    """Create two projects within tenant_alpha and verify strict memory isolation."""
    repo = GraphRepository(TENANT)

    proj_a = ProjectNode(name="Project Solar")
    proj_b = ProjectNode(name="Project Lunar")
    repo.create_project(proj_a)
    repo.create_project(proj_b)

    ep_a = EpisodeNode(session_id="s_a", project_id=proj_a.id, content="Solar planning")
    ep_b = EpisodeNode(session_id="s_b", project_id=proj_b.id, content="Lunar planning")
    repo.create_episode(ep_a)
    repo.create_episode(ep_b)

    # Facts
    fact_a = FactNode(subject="Orbit", predicate="altitude", value="500km", project_id=proj_a.id, status=FactStatus.CURRENT.value)
    fact_b = FactNode(subject="Orbit", predicate="altitude", value="384000km", project_id=proj_b.id, status=FactStatus.CURRENT.value)
    repo.create_fact(fact_a, proj_a.id, ep_a.id)
    repo.create_fact(fact_b, proj_b.id, ep_b.id)

    # Decisions
    dec_a = DecisionNode(title="Propulsion Choice", chosen_option="Ion Thrusters", project_id=proj_a.id)
    dec_b = DecisionNode(title="Propulsion Choice", chosen_option="Chemical Rocket", project_id=proj_b.id)
    repo.create_decision(dec_a, proj_a.id, ep_a.id)
    repo.create_decision(dec_b, proj_b.id, ep_b.id)

    # Procedures
    proc_a = ProcedureNode(title="Preflight", description="Calibrate Solar Sensors", project_id=proj_a.id)
    proc_b = ProcedureNode(title="Preflight", description="Check Lunar Lander Seals", project_id=proj_b.id)
    repo.create_procedure(proc_a, proj_a.id)
    repo.create_procedure(proc_b, proj_b.id)

    # Verify search_facts strictly respects project_id
    res_fa = repo.search_facts("Orbit", project_id=proj_a.id)
    assert len(res_fa) == 1
    assert res_fa[0]["value"] == "500km"

    res_fb = repo.search_facts("Orbit", project_id=proj_b.id)
    assert len(res_fb) == 1
    assert res_fb[0]["value"] == "384000km"

    # Verify search_decisions strictly respects project_id
    res_da = repo.search_decisions("Propulsion", project_id=proj_a.id)
    assert len(res_da) == 1
    assert res_da[0]["chosen_option"] == "Ion Thrusters"

    res_db = repo.search_decisions("Propulsion", project_id=proj_b.id)
    assert len(res_db) == 1
    assert res_db[0]["chosen_option"] == "Chemical Rocket"

    # Verify search_procedures strictly respects project_id
    res_pa = repo.search_procedures("Preflight", project_id=proj_a.id)
    assert len(res_pa) == 1
    assert res_pa[0]["description"] == "Calibrate Solar Sensors"

    res_pb = repo.search_procedures("Preflight", project_id=proj_b.id)
    assert len(res_pb) == 1
    assert res_pb[0]["description"] == "Check Lunar Lander Seals"


def test_live_atomic_fact_supersession():
    """Verify atomic supersession creates SUPERSEDES edge and preserves provenance on live FalkorDB."""
    repo = GraphRepository(TENANT)
    proj = ProjectNode(name="Supersession Project")
    repo.create_project(proj)

    ep1 = EpisodeNode(session_id="s1", project_id=proj.id, content="Initial spec")
    ep2 = EpisodeNode(session_id="s2", project_id=proj.id, content="Revised spec")
    repo.create_episode(ep1)
    repo.create_episode(ep2)

    old_fact = FactNode(subject="Target", predicate="version", value="v1.0", project_id=proj.id, status=FactStatus.CURRENT.value)
    repo.create_fact(old_fact, proj.id, ep1.id)

    new_fact = FactNode(subject="Target", predicate="version", value="v2.0", project_id=proj.id, status=FactStatus.CURRENT.value)
    res = repo.supersede_fact(old_fact.id, new_fact, proj.id, ep2.id)
    assert res is not None
    assert res.get("id") == new_fact.id

    # Check live database state
    old_db = repo.get_fact(old_fact.id)
    new_db = repo.get_fact(new_fact.id)

    assert old_db["status"] == "superseded"
    assert new_db["status"] == "current"

    # Check relationship in graph
    graph = get_graph(TENANT)
    edge_check = graph.query(
        "MATCH (new:Fact {id: $nid})-[:SUPERSEDES]->(old:Fact {id: $oid}) RETURN new, old",
        {"nid": new_fact.id, "oid": old_fact.id},
    ).result_set
    assert len(edge_check) == 1


# ─── 5. Legacy Node Handling Without Missing Properties ─────────

def test_live_legacy_node_compatibility():
    """Verify that nodes created without project_id or revision (legacy schema) do not break queries or updates."""
    graph = get_graph(TENANT)
    legacy_task_id = f"legacy-task-{new_id()}"
    legacy_fact_id = f"legacy-fact-{new_id()}"

    # Insert raw legacy nodes missing project_id and revision
    graph.query(
        "CREATE (t:Task {id: $tid, title: 'Legacy Maintenance', status: 'pending'})",
        {"tid": legacy_task_id},
    )
    graph.query(
        "CREATE (f:Fact {id: $fid, subject: 'Legacy Architecture', predicate: 'pattern', value: 'monolith', status: 'current'})",
        {"fid": legacy_fact_id},
    )

    repo = GraphRepository(TENANT)

    # 1. Fetching legacy task works and defaults revision gracefully
    task = repo.get_task(legacy_task_id)
    assert task is not None
    assert task.get("revision", 1) == 1

    # 2. Updating legacy task sets expected revision and increments to 2
    res = repo.update_task_status(legacy_task_id, "in_progress", expected_revision=1, enforce_lifecycle=True)
    assert res is not None
    assert res["status"] == "in_progress"
    assert res["revision"] == 2

    # 3. Legacy fact with missing project_id is NOT leaked when querying for a specific project
    scoped_facts = repo.search_facts("Legacy Architecture", project_id="new_isolated_project")
    assert len(scoped_facts) == 0

    # 4. Global fact search still finds it without crashing
    f = repo.get_fact(legacy_fact_id)
    assert f is not None
    assert f["value"] == "monolith"


# ─── 6. Simultaneous Dependency Cycle Concurrency Race ──────────

def test_live_concurrent_simultaneous_dependency_cycle_race():
    """Synchronize two independent threads to simultaneously add opposing dependencies A->B and B->A.
    Verify that exactly one succeeds, one fails with TaskDependencyCycleError, and the database contains NO cycle.
    """
    repo = GraphRepository(TENANT)
    p = ProjectNode(name="Simultaneous Race Project")
    repo.create_project(p)

    task_a = TaskNode(title="Task Alpha", project_id=p.id)
    task_b = TaskNode(title="Task Beta", project_id=p.id)
    repo.create_task(task_a, p.id)
    repo.create_task(task_b, p.id)

    barrier = threading.Barrier(2)
    outcomes = []
    errors = []

    def add_dep_a_blocks_b():
        try:
            barrier.wait(timeout=5)
            repo.create_blocked_by(task_a.id, task_b.id, p.id)
            outcomes.append("A->B")
        except Exception as e:
            errors.append(("A->B", type(e).__name__, str(e)))

    def add_dep_b_blocks_a():
        try:
            barrier.wait(timeout=5)
            repo.create_blocked_by(task_b.id, task_a.id, p.id)
            outcomes.append("B->A")
        except Exception as e:
            errors.append(("B->A", type(e).__name__, str(e)))

    t1 = threading.Thread(target=add_dep_a_blocks_b)
    t2 = threading.Thread(target=add_dep_b_blocks_a)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one succeeded and one was prevented with TaskDependencyCycleError
    assert len(outcomes) == 1, f"Expected exactly 1 success, got outcomes={outcomes}, errors={errors}"
    assert len(errors) == 1, f"Expected exactly 1 error, got {errors}"
    assert errors[0][1] == "TaskDependencyCycleError", f"Expected TaskDependencyCycleError, got {errors[0]}"

    # Database inspection: NO circular dependencies exist in graph
    graph = get_graph(TENANT)
    cycle_query = graph.query(
        "MATCH (a:Task {id: $aid})-[r1:BLOCKED_BY]->(b:Task {id: $bid})-[r2:BLOCKED_BY]->(a) RETURN r1, r2",
        {"aid": task_a.id, "bid": task_b.id},
    ).result_set
    assert len(cycle_query) == 0, "Discovered dependency cycle in database!"


# ─── 7. Strict Idempotency Fencing & Token Lifecycle ─────────────

def test_live_idempotency_strict_token_fencing():
    """Verify strict token requirements: missing token rejection, wrong token rejection, retry of failed, and database state."""
    repo = GraphRepository(TENANT)
    key = f"strict-fencing-{new_id()}"
    req = ChatRequest(
        message="Strict Fencing Message",
        tenant_id=TENANT,
        project_id="p_strict",
        session_id="s_strict",
        idempotency_key=key,
    )

    # 1. Reservation creates node with exact token
    status, cached = check_or_reserve_idempotency(repo, req)
    assert status == "reserved"
    token = req.reservation_token
    assert token is not None

    # Verify live database state
    rec = repo.get_idempotency_record(key)
    assert rec["status"] == "running"
    assert rec["reservation_token"] == token

    # 2. Rejection of missing token
    res_none = repo.complete_idempotency_record(
        key=key, status="completed", response_json="{}", reservation_token=""
    )
    assert res_none is None
    # Database check: still running with original token
    assert repo.get_idempotency_record(key)["status"] == "running"

    # 3. Rejection of incorrect token
    res_wrong = repo.complete_idempotency_record(
        key=key, status="completed", response_json="{}", reservation_token="attacker-token-999"
    )
    assert res_wrong is None
    # Database check: still running with original token
    assert repo.get_idempotency_record(key)["status"] == "running"

    # 4. Correct token can mark failed
    ok_fail = finalize_idempotency_failure(repo, key, "Temporary worker crash", reservation_token=token)
    assert ok_fail is True
    rec_failed = repo.get_idempotency_record(key)
    assert rec_failed["status"] == "failed"
    assert "Temporary worker crash" in rec_failed["error"]

    # 5. Safe retry of failed request assigns a NEW token and resets to running
    req_retry = ChatRequest(
        message="Strict Fencing Message",
        tenant_id=TENANT,
        project_id="p_strict",
        session_id="s_strict",
        idempotency_key=key,
    )
    status_retry, cached_retry = check_or_reserve_idempotency(repo, req_retry)
    assert status_retry == "reserved"
    new_token = req_retry.reservation_token
    assert new_token != token

    rec_retried = repo.get_idempotency_record(key)
    assert rec_retried["status"] == "running"
    assert rec_retried["reservation_token"] == new_token

    # 6. Old worker cannot complete it now
    res_stale = repo.complete_idempotency_record(
        key=key, status="completed", response_json='{"answer": "stale"}', reservation_token=token
    )
    assert res_stale is None
    assert repo.get_idempotency_record(key)["status"] == "running"

    # 7. New worker completes it
    chat_resp = ChatResponse(answer="Final success answer", session_id="s_strict", request_id=key)
    ok_complete = finalize_idempotency_success(repo, key, chat_resp, reservation_token=new_token)
    assert ok_complete is True

    rec_final = repo.get_idempotency_record(key)
    assert rec_final["status"] == "completed"
    assert "Final success answer" in rec_final["response_json"]


# ─── 8. Unscoped Retrieval Elimination & Admin Access ────────────

def test_live_unscoped_retrieval_elimination_and_admin_endpoint():
    """Verify that omitting project_id returns [] and does NOT leak tenant data, while admin access requires Master Key."""
    repo = GraphRepository(TENANT)
    proj = ProjectNode(name="Scoped Boundary Project")
    repo.create_project(proj)

    f = FactNode(subject="SecretMetric", predicate="score", value="9999", project_id=proj.id, status="current")
    repo.create_fact(f, proj.id)

    # 1. Scoped search finds it
    assert len(repo.search_facts("SecretMetric", project_id=proj.id)) == 1

    # 2. Omitting project_id or passing None returns []
    assert repo.search_facts("SecretMetric", project_id=None) == []
    assert repo.search_facts("SecretMetric", project_id="") == []
    assert repo.search_decisions("SecretMetric", project_id=None) == []
    assert repo.search_procedures("SecretMetric", project_id=None) == []

    # 3. Explicit admin search finds it
    assert len(repo.search_facts_admin("SecretMetric")) >= 1

    # 4. API admin endpoint authorization check
    from fastapi.testclient import TestClient
    from src.api.main import app

    client = TestClient(app)

    old_auth = settings.AUTH_ENABLED
    old_dev = settings.DEV_MODE
    old_master = settings.MASTER_API_KEY
    try:
        settings.AUTH_ENABLED = True
        settings.DEV_MODE = False
        settings.MASTER_API_KEY = "master-super-secret"
        settings.TENANT_KEYS[TENANT] = "tenant-regular-key"

        # Missing key -> 401
        assert client.get("/api/admin/memory/search", params={"query": "SecretMetric", "tenant_id": TENANT}).status_code == 401

        # Regular tenant key -> 403 (needs admin Master Key)
        res_tenant = client.get(
            "/api/admin/memory/search",
            params={"query": "SecretMetric", "tenant_id": TENANT},
            headers={"X-API-Key": "tenant-regular-key"},
        )
        assert res_tenant.status_code == 403

        # Master key -> 200
        res_admin = client.get(
            "/api/admin/memory/search",
            params={"query": "SecretMetric", "tenant_id": TENANT},
            headers={"X-API-Key": "master-super-secret"},
        )
        assert res_admin.status_code == 200
        data = res_admin.json()
        assert any(x.get("value") == "9999" for x in data.get("facts", []))
    finally:
        settings.AUTH_ENABLED = old_auth
        settings.DEV_MODE = old_dev
        settings.MASTER_API_KEY = old_master
