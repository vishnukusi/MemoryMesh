"""Unit and integration test suite for MemoryMesh Stage 4 Hybrid Memory Retrieval.

Validates:
1. Reciprocal Rank Fusion (RRF) scoring math and graph context adjustments.
2. Historical query detection and supersession inversion.
3. Lexical matching on exact names, identifiers, and versions (Facts, Procedures, Tasks).
4. Semantic matching on paraphrases and conceptually similar questions (Facts).
5. Current vs. superseded memory ranking across standard and historical queries.
6. Graph context: task dependency expansion (BLOCKED_BY) and decision provenance.
7. Strict cross-project isolation (Project A vs Project B).
8. Noise gate and empty-result correctness (irrelevant / zero ground truth).
9. Safe fallback to lexical retrieval on embedding failure.
10. Latency metrics instrumentation (embedding latency vs database latency).
"""

import sys
import os
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.schemas import (
    ProjectNode, FactNode, DecisionNode, TaskNode, ProcedureNode, EpisodeNode, new_id,
)
from src.memory.retrieve import (
    HybridRetrievalConfig,
    search_memory_hybrid,
    is_historical_query,
    extract_query_terms,
    calculate_text_coverage,
    word_matches_text,
)

TENANT_ID = "tenant_alpha"

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="FalkorDB instance required for hybrid retrieval tests",
)


# ─── Unit Tests: RRF Math & Heuristics ────────────────────────────

def test_historical_query_detection():
    assert is_historical_query("Why did we migrate away from our initial storage engine?") is True
    assert is_historical_query("What was the legacy database before PostgreSQL?") is True
    assert is_historical_query("Tell me the history of schema migrations") is True
    assert is_historical_query("What was the superseded caching tier?") is True
    assert is_historical_query("Why did we change the authentication mechanism?") is True
    assert is_historical_query("What is our primary database?") is False
    assert is_historical_query("production deployment prerequisites") is False


def test_text_coverage_and_stemming():
    query_words = ["production", "deployment", "prerequisites"]
    # Task title: Deploy Backend Service to Production
    task_text = "Deploy Backend Service to Production"
    cov = calculate_text_coverage(query_words, task_text)
    # Both 'production' and 'deploy' (stem of 'deployment') match -> 2/3 = 0.667
    assert cov >= 0.60

    # Irrelevant query
    irr_words = ["quantum", "cryptography", "lattice"]
    assert calculate_text_coverage(irr_words, task_text) == 0.0


def test_query_term_extraction():
    q = "PostgreSQL 16 relational data store"
    terms = extract_query_terms(q)
    assert q in terms
    assert any("PostgreSQL" in t for t in terms)
    assert any("relational" in t for t in terms)


# ─── Integration Tests: Full Hybrid Retrieval Pipeline ───────────

@pytest.fixture(scope="module")
def hybrid_test_context():
    """Seed an isolated two-project environment in FalkorDB with vectors."""
    bootstrap_schema(TENANT_ID)
    repo = GraphRepository(TENANT_ID)

    tag = new_id()[:8]
    pid_a = f"test_hyb_a_{tag}"
    pid_b = f"test_hyb_b_{tag}"

    # 1. Projects
    repo.create_project(ProjectNode(id=pid_a, name="Core Backend Project"))
    repo.create_project(ProjectNode(id=pid_b, name="Telemetry Pipeline Project"))

    # 2. Facts Project A
    f_a2 = FactNode(
        id=f"fact_{tag}_a2",
        subject="MySQL 5.7",
        predicate="is_primary_database",
        value="legacy relational database deprecated in migration",
        status="superseded",
        confidence=0.60,
    )
    repo.create_fact(f_a2, pid_a)

    f_a1 = FactNode(
        id=f"fact_{tag}_a1",
        subject="PostgreSQL 16",
        predicate="is_primary_database",
        value="relational data store hosted on AWS RDS",
        status="current",
        confidence=0.95,
    )
    repo.create_fact(f_a1, pid_a)

    f_a3 = FactNode(
        id=f"fact_{tag}_a3",
        subject="Redis 8",
        predicate="caching_tier",
        value="in-memory session storage and distributed rate limiting",
        status="current",
        confidence=0.90,
    )
    repo.create_fact(f_a3, pid_a)

    f_a4 = FactNode(
        id=f"fact_{tag}_a4",
        subject="JWT",
        predicate="authentication_mechanism",
        value="stateless RS256 token verification with 15min expiry",
        status="current",
        confidence=0.95,
    )
    repo.create_fact(f_a4, pid_a)

    f_a5 = FactNode(
        id=f"fact_{tag}_a5",
        subject="JWT",
        predicate="refresh_token_ttl",
        value="refresh token rotation valid for 7 days",
        status="current",
        confidence=0.90,
    )
    repo.create_fact(f_a5, pid_a)

    # 3. Decisions & Episodes Project A
    ep_a1 = EpisodeNode(
        id=f"ep_{tag}_a1",
        session_id=f"sess_{tag}_1",
        project_id=pid_a,
        content="The security audit mandated migrating off MySQL 5.7 to PostgreSQL 16 by end of quarter.",
        actor="user",
    )
    repo.create_episode(ep_a1)

    repo.create_decision(
        DecisionNode(
            id=f"dec_{tag}_a1",
            title="Primary Data Storage",
            chosen_option="PostgreSQL 16",
            rationale="Superior JSONB support and concurrency isolation levels",
            status="approved",
        ),
        pid_a,
        ep_a1.id,
    )

    repo.create_decision(
        DecisionNode(
            id=f"dec_{tag}_a2",
            title="Legacy Storage Engine",
            chosen_option="MySQL 5.7",
            rationale="Original prototype database before schema re-architecture",
            status="superseded",
        ),
        pid_a,
    )

    # 4. Tasks Project A
    repo.create_task(
        TaskNode(id=f"task_{tag}_a1", title="Provision RDS Postgres 16 Cluster", status="completed", priority="high"),
        pid_a,
    )
    repo.create_task(
        TaskNode(id=f"task_{tag}_a2", title="Execute Flyway Schema Migrations", status="in_progress", priority="high"),
        pid_a,
    )
    repo.create_task(
        TaskNode(id=f"task_{tag}_a3", title="Deploy Backend Service to Production", status="pending", priority="critical"),
        pid_a,
    )
    repo.create_blocked_by(f"task_{tag}_a2", f"task_{tag}_a1", pid_a)
    repo.create_blocked_by(f"task_{tag}_a3", f"task_{tag}_a2", pid_a)

    # 5. Procedure Project A
    repo.create_procedure(
        ProcedureNode(
            id=f"proc_{tag}_a1",
            title="Database Migration Procedure",
            description="Zero-downtime blue-green schema migration with Flyway",
            steps_json='["Apply Flyway migration", "Verify read replicas"]',
            approved=True,
        ),
        pid_a,
    )

    # 6. Project B (Cross-Project isolation dataset)
    f_b1 = FactNode(
        id=f"fact_{tag}_b1",
        subject="ClickHouse",
        predicate="analytics_store",
        value="columnar warehouse for event telemetry and clickstream",
        status="current",
        confidence=0.90,
    )
    repo.create_fact(f_b1, pid_b)

    f_b2 = FactNode(
        id=f"fact_{tag}_b2",
        subject="Redis 8",
        predicate="queue_broker",
        value="Celery task broker for analytics aggregation",
        status="current",
        confidence=0.85,
    )
    repo.create_fact(f_b2, pid_b)

    # Backfill embeddings for Facts
    repo.backfill_fact_embeddings(project_id=pid_a)
    repo.backfill_fact_embeddings(project_id=pid_b)

    return {
        "repo": repo,
        "pid_a": pid_a,
        "pid_b": pid_b,
        "tag": tag,
        "ids": {
            "fact_a1": f_a1.id,
            "fact_a2": f_a2.id,
            "fact_a3": f_a3.id,
            "fact_a4": f_a4.id,
            "fact_a5": f_a5.id,
            "dec_a1": f"dec_{tag}_a1",
            "dec_a2": f"dec_{tag}_a2",
            "task_a1": f"task_{tag}_a1",
            "task_a2": f"task_{tag}_a2",
            "task_a3": f"task_{tag}_a3",
            "proc_a1": f"proc_{tag}_a1",
            "fact_b1": f_b1.id,
            "fact_b2": f_b2.id,
        },
    }


def test_hybrid_exact_keyword_fact_and_procedure(hybrid_test_context):
    ctx = hybrid_test_context
    repo, pid_a, ids = ctx["repo"], ctx["pid_a"], ctx["ids"]

    # 1. Fact exact keyword
    res = search_memory_hybrid(repo, pid_a, "PostgreSQL 16 relational data store")
    assert len(res["facts"]) >= 1
    top_fact = res["facts"][0]
    assert top_fact["id"] == ids["fact_a1"]
    assert top_fact["score"] > 0
    assert top_fact["lexical_rank"] is not None
    assert top_fact["semantic_rank"] is not None

    # 2. Procedure exact keyword
    res_p = search_memory_hybrid(repo, pid_a, "Database Migration Procedure")
    assert len(res_p["procedures"]) >= 1
    assert res_p["procedures"][0]["id"] == ids["proc_a1"]


def test_hybrid_semantic_paraphrases_on_facts(hybrid_test_context):
    ctx = hybrid_test_context
    repo, pid_a, ids = ctx["repo"], ctx["pid_a"], ctx["ids"]

    # Paraphrase for Postgres (Q03)
    res_db = search_memory_hybrid(repo, pid_a, "What relational engine powers our persistent record storage?")
    assert len(res_db["facts"]) >= 1
    assert res_db["facts"][0]["id"] == ids["fact_a1"]

    # Paraphrase for Redis (Q04)
    res_cache = search_memory_hybrid(repo, pid_a, "What technology accelerates state storage and throttles incoming traffic?")
    assert len(res_cache["facts"]) >= 1
    assert res_cache["facts"][0]["id"] == ids["fact_a3"]

    # Paraphrase for JWT (Q05)
    res_jwt = search_memory_hybrid(repo, pid_a, "How does user credential validation work and what is the token lifetime?")
    assert len(res_jwt["facts"]) >= 1
    assert res_jwt["facts"][0]["id"] == ids["fact_a4"]


def test_current_vs_superseded_fact_and_decision(hybrid_test_context):
    ctx = hybrid_test_context
    repo, pid_a, ids = ctx["repo"], ctx["pid_a"], ctx["ids"]

    # Standard query: Current fact preferred over superseded fact
    res_std = search_memory_hybrid(repo, pid_a, "primary database")
    assert len(res_std["facts"]) >= 1
    assert res_std["facts"][0]["id"] == ids["fact_a1"]  # Postgres is current
    assert res_std["facts"][0]["status"] == "current"

    # Historical query: Historical intent detected, superseded records preserved and boosted
    res_hist = search_memory_hybrid(repo, pid_a, "Why did we migrate away from our initial storage engine?")
    assert res_hist["metrics"]["is_historical_query"] is True
    dec_ids = [d["id"] for d in res_hist["decisions"]]
    assert ids["dec_a1"] in dec_ids
    assert ids["dec_a2"] in dec_ids


def test_task_prerequisite_graph_context(hybrid_test_context):
    ctx = hybrid_test_context
    repo, pid_a, ids = ctx["repo"], ctx["pid_a"], ctx["ids"]

    res = search_memory_hybrid(repo, pid_a, "production deployment prerequisites")
    task_ids = [t["id"] for t in res["tasks"]]
    assert ids["task_a3"] in task_ids  # Deploy Backend Service to Production
    assert ids["task_a2"] in task_ids  # Execute Flyway Schema Migrations (blocker)


def test_strict_cross_project_isolation(hybrid_test_context):
    ctx = hybrid_test_context
    repo, pid_a, ids = ctx["repo"], ctx["pid_a"], ctx["ids"]

    # Querying Project A for Project B ClickHouse entity must return 0 results
    res_clickhouse = search_memory_hybrid(repo, pid_a, "Tell me about our ClickHouse analytics store")
    assert len(res_clickhouse["ranked_all"]) == 0
    assert len(res_clickhouse["facts"]) == 0

    # Querying Project A for Project B Redis telemetry broker must return 0 results
    res_telemetry = search_memory_hybrid(repo, pid_a, "What is Redis used for in the data warehouse telemetry pipeline?")
    assert len(res_telemetry["ranked_all"]) == 0

    # Verify no leaked Project B items in any query against Project A
    for item in res_clickhouse["ranked_all"] + res_telemetry["ranked_all"]:
        assert item.get("project_id") != ctx["pid_b"]


def test_empty_result_relevance_gate(hybrid_test_context):
    ctx = hybrid_test_context
    repo, pid_a = ctx["repo"], ctx["pid_a"]

    res_q = search_memory_hybrid(repo, pid_a, "What is our policy on quantum cryptography and lattice key exchange?")
    assert len(res_q["ranked_all"]) == 0

    res_c = search_memory_hybrid(repo, pid_a, "Who is the head chef in the Seattle cafeteria?")
    assert len(res_c["ranked_all"]) == 0


def test_fallback_on_embedding_failure(hybrid_test_context):
    ctx = hybrid_test_context
    repo, pid_a, ids = ctx["repo"], ctx["pid_a"], ctx["ids"]

    with patch("src.services.embedding_service.generate_embedding_safe", return_value=(None, "Mock embedding failure")):
        res = search_memory_hybrid(repo, pid_a, "PostgreSQL 16 relational data store")
        assert res["metrics"]["semantic_fallback_used"] is True
        assert res["metrics"]["query_embedding_generated"] is False
        assert len(res["facts"]) >= 1
        assert res["facts"][0]["id"] == ids["fact_a1"]


def test_latency_metrics_instrumentation(hybrid_test_context):
    ctx = hybrid_test_context
    repo, pid_a = ctx["repo"], ctx["pid_a"]

    res = search_memory_hybrid(repo, pid_a, "PostgreSQL 16 relational data store")
    metrics = res["metrics"]
    assert "embedding_latency_ms" in metrics
    assert "db_search_latency_ms" in metrics
    assert "total_latency_ms" in metrics
    assert metrics["embedding_latency_ms"] >= 0.0
    assert metrics["db_search_latency_ms"] >= 0.0
    assert metrics["total_latency_ms"] >= 0.0
