"""Tests for Stage 3 Semantic Memory Retrieval in MemoryMesh.

Covers:
1. Embedding service unit tests (dimension validation, timeout, model health, non-numerical rejection).
2. Semantic similarity for paraphrases with zero lexical overlap.
3. Exact keyword queries.
4. Distinguishing similar memories (e.g. access token vs refresh token TTL).
5. Project A vs Project B strict isolation (zero cross-project leakage).
6. Irrelevant / empty queries (zero false positive returns).
7. Idempotent and restartable backfill for existing Facts.
8. Safe fallback to lexical retrieval on embedding service failure.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.memory.retrieve import search_memory, search_memory_semantic
from src.schemas import ProjectNode, FactNode, new_id
from src.services.embedding_service import (
    get_embedding,
    generate_embedding_safe,
    check_embedding_health,
    format_fact_for_embedding,
    format_query_for_embedding,
    cosine_similarity,
    cosine_distance,
    EmbeddingError,
    EmbeddingDimensionMismatchError,
    EmbeddingTimeoutError,
    EmbeddingUnavailableError,
)

TENANT_ID = "tenant_alpha"

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="Live FalkorDB instance required for semantic retrieval tests",
)


@pytest.fixture(autouse=True)
def ensure_schema():
    bootstrap_schema(TENANT_ID)


# ─── 1. Embedding Service Unit Tests ─────────────────────────────

def test_embedding_health_and_dimension():
    """Verify Ollama nomic-embed-text is available and produces 768 dimensions."""
    health = check_embedding_health()
    assert health["available"] is True, f"Embedding service not available: {health.get('error')}"
    assert health["model"] == "nomic-embed-text"
    assert health["dimension"] == 768


def test_format_fact_and_query_canonical_representation():
    """Verify deterministic canonical text formatting."""
    text = format_fact_for_embedding(" PostgreSQL 16 ", " is_primary_database ", " relational store ")
    assert text == "PostgreSQL 16 is_primary_database relational store"

    q = format_query_for_embedding("  what is our database?  ")
    assert q == "what is our database?"

    with pytest.raises(ValueError, match="empty"):
        get_embedding("   ")


def test_embedding_dimension_validation(monkeypatch):
    """Mismatched embedding dimensions must raise EmbeddingDimensionMismatchError."""
    fake_client = MagicMock()
    fake_client.embeddings.return_value = {"embedding": [0.1] * 512}  # expected 768
    monkeypatch.setattr("ollama.Client", lambda *args, **kwargs: fake_client)

    with pytest.raises(EmbeddingDimensionMismatchError, match="dimension mismatch"):
        get_embedding("Test prompt")


def test_embedding_timeout_handling(monkeypatch):
    """Simulated timeout must raise EmbeddingTimeoutError."""
    import time

    def slow_embeddings(*args, **kwargs):
        time.sleep(2.0)
        return {"embedding": [0.1] * 768}

    fake_client = MagicMock()
    fake_client.embeddings.side_effect = slow_embeddings
    monkeypatch.setattr("ollama.Client", lambda *args, **kwargs: fake_client)

    with pytest.raises(EmbeddingTimeoutError):
        get_embedding("Test timeout", timeout=1)


def test_cosine_similarity_math():
    """Verify cosine similarity calculation accuracy and bounds."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v2)) == 1.0
    assert pytest.approx(cosine_distance(v1, v2)) == 0.0

    v_orth = [0.0, 1.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v_orth)) == 0.0

    v_opp = [-1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v_opp)) == -1.0


# ─── 2. Semantic Fact Retrieval & Backfill Tests ─────────────────

def test_semantic_retrieval_paraphrase_and_exact_match():
    """Verify semantic retrieval succeeds where lexical search misses on paraphrases."""
    repo = GraphRepository(TENANT_ID)
    pid = f"proj_sem_{new_id()[:8]}"
    repo.create_project(ProjectNode(id=pid, name="Semantic Test Project"))

    # Create un-embedded facts
    f_redis = FactNode(
        subject="Redis 8",
        predicate="caching_tier",
        value="in-memory session storage and distributed rate limiting",
        status="current",
        confidence=0.95,
    )
    f_pg = FactNode(
        subject="PostgreSQL 16",
        predicate="is_primary_database",
        value="relational data store hosted on AWS RDS",
        status="current",
        confidence=0.95,
    )
    repo.create_fact(f_redis, pid)
    repo.create_fact(f_pg, pid)

    # 1. Backfill embeddings for project
    backfill_res = repo.backfill_fact_embeddings(project_id=pid)
    assert backfill_res["total_embedded"] == 2
    assert backfill_res["is_complete"] is True

    # 2. Second backfill must be idempotent (0 un-embedded nodes)
    repeat_res = repo.backfill_fact_embeddings(project_id=pid)
    assert repeat_res["total_processed"] == 0
    assert repeat_res["total_embedded"] == 0

    # 3. Query: Semantic Paraphrase (zero exact keywords in common with Redis)
    query_text = "What technology accelerates state storage and throttles incoming traffic?"

    # Lexical baseline fails:
    lex_res = repo.search_facts(query_text, project_id=pid)
    assert len(lex_res) == 0, "Expected lexical search to miss the paraphrase"

    # Semantic retrieval succeeds:
    sem_res = search_memory_semantic(repo, project_id=pid, query=query_text, limit=3)
    assert sem_res["query_embedding_generated"] is True
    assert sem_res["fallback_used"] is False
    assert len(sem_res["facts"]) >= 1

    top_fact = sem_res["facts"][0]
    assert top_fact["id"] == f_redis.id
    assert "Redis 8" in top_fact["subject"]
    assert top_fact["similarity"] > 0.50

    # 4. Query: Exact match on PostgreSQL 16
    pg_query = "PostgreSQL 16 relational data store"
    sem_pg = search_memory_semantic(repo, project_id=pid, query=pg_query, limit=3)
    assert len(sem_pg["facts"]) >= 1
    assert sem_pg["facts"][0]["id"] == f_pg.id


def test_semantic_distinguishing_similar_memories():
    """Semantic search must distinguish access token TTL (15min) from refresh token TTL (7 days)."""
    repo = GraphRepository(TENANT_ID)
    pid = f"proj_tokens_{new_id()[:8]}"
    repo.create_project(ProjectNode(id=pid, name="Token Test Project"))

    f_access = FactNode(
        subject="JWT",
        predicate="authentication_mechanism",
        value="stateless RS256 token verification with 15min expiry",
        status="current",
    )
    f_refresh = FactNode(
        subject="JWT",
        predicate="refresh_token_ttl",
        value="refresh token rotation valid for 7 days",
        status="current",
    )
    repo.create_fact(f_access, pid)
    repo.create_fact(f_refresh, pid)
    repo.backfill_fact_embeddings(project_id=pid)

    # Query specifically about refresh tokens
    res = search_memory_semantic(
        repo,
        project_id=pid,
        query="How long are refresh tokens valid before re-authentication?",
        limit=2,
    )
    assert len(res["facts"]) >= 1
    assert res["facts"][0]["id"] == f_refresh.id
    assert "7 days" in res["facts"][0]["value"]


def test_project_isolation_in_semantic_search():
    """Semantic search in Project A must NEVER return facts from Project B, even if highly similar."""
    repo = GraphRepository(TENANT_ID)
    pid_a = f"proj_iso_a_{new_id()[:8]}"
    pid_b = f"proj_iso_b_{new_id()[:8]}"
    repo.create_project(ProjectNode(id=pid_a, name="Project A"))
    repo.create_project(ProjectNode(id=pid_b, name="Project B"))

    # Project B has ClickHouse
    f_clickhouse = FactNode(
        subject="ClickHouse",
        predicate="analytics_store",
        value="columnar warehouse for event telemetry and clickstream",
        status="current",
    )
    repo.create_fact(f_clickhouse, pid_b)
    repo.backfill_fact_embeddings(project_id=pid_b)

    # Project A has no ClickHouse facts
    f_pg = FactNode(
        subject="PostgreSQL 16",
        predicate="is_primary_database",
        value="relational data store",
        status="current",
    )
    repo.create_fact(f_pg, pid_a)
    repo.backfill_fact_embeddings(project_id=pid_a)

    # Query Project A asking about ClickHouse
    res_a = search_memory_semantic(
        repo,
        project_id=pid_a,
        query="Tell me about our ClickHouse analytics store",
        limit=5,
    )
    # Must return 0 facts from Project B
    for f in res_a["facts"]:
        assert f.get("project_id") != pid_b
        assert "ClickHouse" not in f.get("subject", "")

    # Querying Project B directly returns ClickHouse
    res_b = search_memory_semantic(
        repo,
        project_id=pid_b,
        query="Tell me about our ClickHouse analytics store",
        limit=5,
    )
    assert len(res_b["facts"]) >= 1
    assert res_b["facts"][0]["id"] == f_clickhouse.id


def test_irrelevant_query_relevance_gate():
    """Unrelated queries must be filtered out by the minimum similarity threshold."""
    repo = GraphRepository(TENANT_ID)
    pid = f"proj_noise_{new_id()[:8]}"
    repo.create_project(ProjectNode(id=pid, name="Noise Test Project"))

    f = FactNode(subject="PostgreSQL", predicate="type", value="relational database", status="current")
    repo.create_fact(f, pid)
    repo.backfill_fact_embeddings(project_id=pid)

    res = search_memory_semantic(
        repo,
        project_id=pid,
        query="Who is the head chef in the Seattle cafeteria?",
        min_similarity=0.55,
    )
    assert len(res["facts"]) == 0, "Unrelated query should not pass minimum similarity threshold"


def test_safe_fallback_on_embedding_failure(monkeypatch):
    """When embedding generation fails, search_memory_semantic must gracefully fall back to lexical."""
    repo = GraphRepository(TENANT_ID)
    pid = f"proj_fallback_{new_id()[:8]}"
    repo.create_project(ProjectNode(id=pid, name="Fallback Project"))

    f = FactNode(subject="RabbitMQ", predicate="messaging", value="AMQP queue broker", status="current")
    repo.create_fact(f, pid)

    # Simulate Ollama connection failure
    def mock_fail(*args, **kwargs):
        raise RuntimeError("Simulated Ollama connection timeout")

    monkeypatch.setattr("src.services.embedding_service.get_embedding", mock_fail)

    res = search_memory_semantic(repo, project_id=pid, query="RabbitMQ", limit=5)
    assert res["fallback_used"] is True
    assert res["query_embedding_generated"] is False
    assert "Simulated Ollama connection timeout" in res["error"]
    assert len(res["facts"]) >= 1
    assert res["facts"][0]["id"] == f.id
