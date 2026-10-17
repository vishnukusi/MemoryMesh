"""Deterministic baseline evaluation suite for MemoryMesh retrieval.

Stage 2 of Hybrid Memory Retrieval:
Measures the existing keyword / substring CONTAINS retrieval implementation
against a deterministic ground-truth evaluation dataset BEFORE implementing
hybrid semantic search.

Metrics measured:
- Recall@3 and Recall@5
- Precision@3 and Precision@5
- Mean Reciprocal Rank (MRR)
- Missed relevant memories count
- Cross-project leakage count
- Zero-match handling (empty result correctness)
- Retrieval latency (ms)
"""

import os
import sys
import time
from typing import Dict, List, Any, Set, Tuple
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.memory.retrieve import search_memory
from src.schemas import (
    ProjectNode, FactNode, DecisionNode, TaskNode, ProcedureNode, EpisodeNode, new_id,
)

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="FalkorDB instance required for retrieval baseline evaluation",
)

TENANT_ID = "tenant_alpha"


# ─── Ground Truth Benchmark Dataset Definition ───────────────────

class BenchmarkQuery:
    def __init__(
        self,
        qid: str,
        query: str,
        category: str,
        target_project_label: str,  # "A" or "B"
        expected_ids: List[str],
        expected_type: str,  # "Fact", "Decision", "Task", "Procedure", "Episode", or "None"
        description: str,
    ):
        self.qid = qid
        self.query = query
        self.category = category
        self.target_project_label = target_project_label
        self.expected_ids = set(expected_ids)
        self.expected_type = expected_type
        self.description = description


BENCHMARK_QUERIES = [
    # ── Category 1: Exact Keyword Matches ──
    BenchmarkQuery(
        qid="Q01_EXACT_KEYWORD_FACT",
        query="PostgreSQL 16 relational data store",
        category="Exact Keyword",
        target_project_label="A",
        expected_ids=["fact_a1"],
        expected_type="Fact",
        description="Exact match on subject and value of active database fact",
    ),
    BenchmarkQuery(
        qid="Q02_EXACT_KEYWORD_PROC",
        query="Database Migration Procedure",
        category="Exact Keyword",
        target_project_label="A",
        expected_ids=["proc_a1"],
        expected_type="Procedure",
        description="Exact match on title of schema migration procedure",
    ),

    # ── Category 2: Semantic Paraphrases / Synonyms ──
    BenchmarkQuery(
        qid="Q03_PARAPHRASE_DATABASE",
        query="What relational engine powers our persistent record storage?",
        category="Semantic Paraphrase",
        target_project_label="A",
        expected_ids=["fact_a1"],
        expected_type="Fact",
        description="Paraphrase of primary database fact without using 'Postgres' or 'RDS'",
    ),
    BenchmarkQuery(
        qid="Q04_PARAPHRASE_CACHE",
        query="What technology accelerates state storage and throttles incoming traffic?",
        category="Semantic Paraphrase",
        target_project_label="A",
        expected_ids=["fact_a3"],
        expected_type="Fact",
        description="Paraphrase of Redis caching and rate limiting fact",
    ),
    BenchmarkQuery(
        qid="Q05_PARAPHRASE_AUTH",
        query="How does user credential validation work and what is the token lifetime?",
        category="Semantic Paraphrase",
        target_project_label="A",
        expected_ids=["fact_a4"],
        expected_type="Fact",
        description="Paraphrase of JWT stateless RS256 authentication fact",
    ),
    BenchmarkQuery(
        qid="Q06_PARAPHRASE_GATEWAY",
        query="What reverse proxy directs ingress network calls?",
        category="Semantic Paraphrase",
        target_project_label="A",
        expected_ids=["dec_a3"],
        expected_type="Decision",
        description="Paraphrase of Envoy Proxy API Gateway decision",
    ),

    # ── Category 3: Distinguishing Similar Memories ──
    BenchmarkQuery(
        qid="Q07_SIMILAR_TOKEN_TTL",
        query="How long are refresh tokens valid before re-authentication?",
        category="Similar Memories",
        target_project_label="A",
        expected_ids=["fact_a5"],
        expected_type="Fact",
        description="Distinguish 7-day refresh token TTL from 15-minute access token TTL",
    ),

    # ── Category 4: Current vs. Superseded Facts ──
    BenchmarkQuery(
        qid="Q08_CURRENT_VS_SUPERSEDED",
        query="primary database",
        category="Current vs Superseded",
        target_project_label="A",
        expected_ids=["fact_a1"],
        expected_type="Fact",
        description="Must retrieve active PostgreSQL 16 fact rather than superseded MySQL fact",
    ),

    # ── Category 5: Cross-Project Isolation (Project A vs Project B) ──
    BenchmarkQuery(
        qid="Q09_ISOLATION_REDIS_TELEMETRY",
        query="What is Redis used for in the data warehouse telemetry pipeline?",
        category="Cross-Project Isolation",
        target_project_label="A",
        expected_ids=[],  # Redis Celery broker is in Project B, not Project A!
        expected_type="None",
        description="Searching Project A for Project B's Redis telemetry broker must return 0 results",
    ),
    BenchmarkQuery(
        qid="Q10_ISOLATION_CLICKHOUSE",
        query="Tell me about our ClickHouse analytics store",
        category="Cross-Project Isolation",
        target_project_label="A",
        expected_ids=[],  # ClickHouse is in Project B, not Project A!
        expected_type="None",
        description="Searching Project A for Project B's ClickHouse store must return 0 results",
    ),

    # ── Category 6: Empty / Zero-Match / Irrelevant Queries ──
    BenchmarkQuery(
        qid="Q11_UNRELATED_QUANTUM",
        query="What is our policy on quantum cryptography and lattice key exchange?",
        category="Irrelevant / Zero Ground Truth",
        target_project_label="A",
        expected_ids=[],
        expected_type="None",
        description="Completely unrelated topic with zero relevant records in database",
    ),
    BenchmarkQuery(
        qid="Q12_UNRELATED_CAFETERIA",
        query="Who is the head chef in the Seattle cafeteria?",
        category="Irrelevant / Zero Ground Truth",
        target_project_label="A",
        expected_ids=[],
        expected_type="None",
        description="Out-of-domain conversational query with zero relevant records",
    ),

    # ── Category 7: Tasks and Dependency Queries ──
    BenchmarkQuery(
        qid="Q13_TASK_PREREQUISITES",
        query="production deployment prerequisites",
        category="Task Dependencies",
        target_project_label="A",
        expected_ids=["task_a3", "task_a2"],
        expected_type="Task",
        description="Find production deploy task and its prerequisite migration task",
    ),

    # ── Category 8: Conflicting or Superseded Decisions ──
    BenchmarkQuery(
        qid="Q14_SUPERSEDED_DECISION",
        query="Why did we migrate away from our initial storage engine?",
        category="Conflicting Decisions",
        target_project_label="A",
        expected_ids=["dec_a1", "dec_a2"],
        expected_type="Decision",
        description="Retrieve active and historical decisions regarding the database migration",
    ),
]


# ─── Metric Computation Helpers ─────────────────────────────────

def calculate_metrics_for_query(
    retrieved_ids: List[str],
    expected_ids: Set[str],
    k_values: Tuple[int, int] = (3, 5),
) -> Dict[str, Any]:
    """Calculate Recall@K, Precision@K, and Reciprocal Rank for a single query."""
    is_empty_gt = len(expected_ids) == 0

    if is_empty_gt:
        # Ground truth is empty:
        # If retrieved count is 0, precision is 1.0 (correctly empty). If retrieved > 0, precision is 0.0.
        # Recall is 1.0 (all 0 relevant items were retrieved).
        # MRR is undefined for empty GT (excluded from mean).
        p3 = 1.0 if len(retrieved_ids[:3]) == 0 else 0.0
        p5 = 1.0 if len(retrieved_ids[:5]) == 0 else 0.0
        r3 = 1.0 if len(retrieved_ids[:3]) == 0 else 0.0
        r5 = 1.0 if len(retrieved_ids[:5]) == 0 else 0.0
        rr = None
        missed = 0
    else:
        # Non-empty ground truth
        top3 = retrieved_ids[:3]
        top5 = retrieved_ids[:5]

        hits3 = len(set(top3) & expected_ids)
        hits5 = len(set(top5) & expected_ids)

        r3 = hits3 / len(expected_ids)
        r5 = hits5 / len(expected_ids)

        # Standard IR precision: hits / K
        p3 = hits3 / 3.0
        p5 = hits5 / 5.0

        # Reciprocal Rank (first relevant item)
        rr = 0.0
        for rank, rid in enumerate(retrieved_ids, 1):
            if rid in expected_ids:
                rr = 1.0 / rank
                break

        all_hits = len(set(retrieved_ids) & expected_ids)
        missed = len(expected_ids) - all_hits

    return {
        "is_empty_gt": is_empty_gt,
        "recall@3": r3,
        "recall@5": r5,
        "precision@3": p3,
        "precision@5": p5,
        "reciprocal_rank": rr,
        "missed": missed,
    }


# ─── Fixture: Seed Isolated Test Environment ─────────────────────

@pytest.fixture(scope="module")
def eval_env():
    """Seed isolated project A and project B datasets into live FalkorDB."""
    bootstrap_schema(TENANT_ID)
    repo = GraphRepository(TENANT_ID)

    # Unique execution run tag to avoid collisions
    run_tag = new_id()[:8]
    pid_a = f"eval_proj_a_{run_tag}"
    pid_b = f"eval_proj_b_{run_tag}"

    # Map logical IDs to graph node IDs
    id_map: Dict[str, str] = {
        "fact_a1": f"{run_tag}_fact_a1",
        "fact_a2": f"{run_tag}_fact_a2",
        "fact_a3": f"{run_tag}_fact_a3",
        "fact_a4": f"{run_tag}_fact_a4",
        "fact_a5": f"{run_tag}_fact_a5",
        "dec_a1": f"{run_tag}_dec_a1",
        "dec_a2": f"{run_tag}_dec_a2",
        "dec_a3": f"{run_tag}_dec_a3",
        "task_a1": f"{run_tag}_task_a1",
        "task_a2": f"{run_tag}_task_a2",
        "task_a3": f"{run_tag}_task_a3",
        "proc_a1": f"{run_tag}_proc_a1",
        "ep_a1": f"{run_tag}_ep_a1",
        "ep_a2": f"{run_tag}_ep_a2",
        "fact_b1": f"{run_tag}_fact_b1",
        "fact_b2": f"{run_tag}_fact_b2",
        "dec_b1": f"{run_tag}_dec_b1",
        "task_b1": f"{run_tag}_task_b1",
    }

    # 1. Create Projects
    repo.create_project(ProjectNode(id=pid_a, name="Core Backend & Infrastructure"))
    repo.create_project(ProjectNode(id=pid_b, name="Analytics & Telemetry Pipeline"))

    # 2. Seed Project A Facts
    repo.create_fact(
        FactNode(
            id=id_map["fact_a2"],
            subject="MySQL 5.7",
            predicate="is_primary_database",
            value="legacy relational database deprecated in migration",
            status="current",
            confidence=0.60,
        ),
        pid_a,
    )
    fact_a1_node = FactNode(
        id=id_map["fact_a1"],
        subject="PostgreSQL 16",
        predicate="is_primary_database",
        value="relational data store hosted on AWS RDS",
        status="current",
        confidence=0.95,
    )
    repo.supersede_fact(id_map["fact_a2"], fact_a1_node, pid_a)

    repo.create_fact(
        FactNode(
            id=id_map["fact_a3"],
            subject="Redis 8",
            predicate="caching_tier",
            value="in-memory session storage and distributed rate limiting",
            status="current",
            confidence=0.90,
        ),
        pid_a,
    )
    repo.create_fact(
        FactNode(
            id=id_map["fact_a4"],
            subject="JWT",
            predicate="authentication_mechanism",
            value="stateless RS256 token verification with 15min expiry",
            status="current",
            confidence=0.95,
        ),
        pid_a,
    )
    repo.create_fact(
        FactNode(
            id=id_map["fact_a5"],
            subject="JWT",
            predicate="refresh_token_ttl",
            value="refresh token rotation valid for 7 days",
            status="current",
            confidence=0.90,
        ),
        pid_a,
    )

    # 3. Seed Project A Episodes & Decisions
    repo.create_episode(
        EpisodeNode(
            id=id_map["ep_a1"],
            session_id=f"sess_{run_tag}_1",
            project_id=pid_a,
            content="The security audit mandated migrating off MySQL 5.7 to PostgreSQL 16 by end of quarter.",
            actor="user",
        )
    )
    repo.create_episode(
        EpisodeNode(
            id=id_map["ep_a2"],
            session_id=f"sess_{run_tag}_2",
            project_id=pid_a,
            content="Team confirmed Envoy Proxy handles all ingress traffic with rate limiting in front of Redis.",
            actor="user",
        )
    )

    repo.create_decision(
        DecisionNode(
            id=id_map["dec_a1"],
            title="Primary Data Storage",
            chosen_option="PostgreSQL 16",
            rationale="Superior JSONB support and concurrency isolation levels",
            status="approved",
        ),
        pid_a,
        id_map["ep_a1"],
    )
    repo.create_decision(
        DecisionNode(
            id=id_map["dec_a2"],
            title="Legacy Storage Engine",
            chosen_option="MySQL 5.7",
            rationale="Original prototype database before schema re-architecture",
            status="superseded",
        ),
        pid_a,
    )
    repo.create_decision(
        DecisionNode(
            id=id_map["dec_a3"],
            title="API Gateway Architecture",
            chosen_option="Envoy Proxy",
            rationale="High-throughput gRPC and HTTP/2 multiplexing",
            status="approved",
        ),
        pid_a,
        id_map["ep_a2"],
    )

    # 4. Seed Project A Tasks & Dependencies
    repo.create_task(
        TaskNode(
            id=id_map["task_a1"],
            title="Provision RDS Postgres 16 Cluster",
            status="completed",
            priority="high",
        ),
        pid_a,
    )
    repo.create_task(
        TaskNode(
            id=id_map["task_a2"],
            title="Execute Flyway Schema Migrations",
            status="in_progress",
            priority="high",
        ),
        pid_a,
    )
    repo.create_task(
        TaskNode(
            id=id_map["task_a3"],
            title="Deploy Backend Service to Production",
            status="pending",
            priority="critical",
        ),
        pid_a,
    )
    repo.create_blocked_by(id_map["task_a2"], id_map["task_a1"], pid_a)
    repo.create_blocked_by(id_map["task_a3"], id_map["task_a2"], pid_a)

    # 5. Seed Project A Procedure
    repo.create_procedure(
        ProcedureNode(
            id=id_map["proc_a1"],
            title="Database Migration Procedure",
            description="Zero-downtime blue-green schema migration with Flyway",
            steps_json='["Run pre-migration validation", "Apply Flyway migration", "Verify read replicas", "Switch application traffic"]',
            approved=True,
        ),
        pid_a,
    )

    # 6. Seed Project B (Cross-Project Isolation Dataset)
    repo.create_fact(
        FactNode(
            id=id_map["fact_b1"],
            subject="ClickHouse",
            predicate="analytics_store",
            value="columnar warehouse for event telemetry and clickstream",
            status="current",
            confidence=0.90,
        ),
        pid_b,
    )
    repo.create_fact(
        FactNode(
            id=id_map["fact_b2"],
            subject="Redis 8",
            predicate="queue_broker",
            value="Celery task broker for analytics aggregation",
            status="current",
            confidence=0.85,
        ),
        pid_b,
    )
    repo.create_decision(
        DecisionNode(
            id=id_map["dec_b1"],
            title="Data Warehouse Selection",
            chosen_option="ClickHouse",
            rationale="High ingestion rate for time-series logs",
            status="approved",
        ),
        pid_b,
    )
    repo.create_task(
        TaskNode(
            id=id_map["task_b1"],
            title="Deploy ClickHouse Cluster",
            status="in_progress",
            priority="medium",
        ),
        pid_b,
    )

    yield {
        "repo": repo,
        "pid_a": pid_a,
        "pid_b": pid_b,
        "id_map": id_map,
        "reverse_id_map": {v: k for k, v in id_map.items()},
    }


# ─── Benchmark Test Execution ───────────────────────────────────

def test_retrieval_baseline_suite(eval_env):
    """Execute all 14 benchmark queries against current lexical retrieval and compute baseline metrics."""
    repo = eval_env["repo"]
    pid_a = eval_env["pid_a"]
    pid_b = eval_env["pid_b"]
    id_map = eval_env["id_map"]
    rev_id_map = eval_env["reverse_id_map"]

    results = []
    latencies = []
    cross_project_leaks = 0

    print("\n" + "=" * 95)
    print(f"{'QID':<28} | {'Category':<22} | {'R@3':<5} | {'R@5':<5} | {'P@3':<5} | {'P@5':<5} | {'RR':<5} | {'Latency':<7}")
    print("-" * 95)

    for bq in BENCHMARK_QUERIES:
        target_pid = pid_a if bq.target_project_label == "A" else pid_b
        expected_actual_ids = {id_map[lid] for lid in bq.expected_ids}

        # Measure pure database retrieval latency
        t0 = time.perf_counter()
        mem_results = search_memory(repo, project_id=target_pid, query=bq.query)
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies.append(latency_ms)

        # Flatten retrieved IDs in consistent order: facts -> decisions -> tasks -> procedures -> episodes
        all_retrieved: List[Dict[str, Any]] = []
        if bq.expected_type == "Fact":
            all_retrieved = mem_results.get("facts", [])
        elif bq.expected_type == "Decision":
            all_retrieved = mem_results.get("decisions", [])
        elif bq.expected_type == "Task":
            all_retrieved = mem_results.get("tasks", [])
        elif bq.expected_type == "Procedure":
            all_retrieved = mem_results.get("procedures", [])
        elif bq.expected_type == "Episode":
            all_retrieved = mem_results.get("episodes", [])
        else:
            # Query with no specific expected type or empty ground truth: pool all results
            all_retrieved = (
                mem_results.get("facts", []) +
                mem_results.get("decisions", []) +
                mem_results.get("tasks", []) +
                mem_results.get("procedures", []) +
                mem_results.get("episodes", [])
            )

        retrieved_ids = [item.get("id") for item in all_retrieved if item.get("id")]

        # Verify cross-project isolation: no retrieved item must belong to a different project
        for item in all_retrieved:
            item_proj = item.get("project_id")
            if item_proj and item_proj != target_pid:
                cross_project_leaks += 1

        # Compute query metrics
        metrics = calculate_metrics_for_query(retrieved_ids, expected_actual_ids)
        metrics["qid"] = bq.qid
        metrics["category"] = bq.category
        metrics["latency_ms"] = latency_ms
        metrics["retrieved_count"] = len(retrieved_ids)
        metrics["expected_count"] = len(expected_actual_ids)
        results.append(metrics)

        rr_str = f"{metrics['reciprocal_rank']:.2f}" if metrics['reciprocal_rank'] is not None else "N/A"
        print(
            f"{bq.qid:<28} | {bq.category:<22} | {metrics['recall@3']:<5.2f} | {metrics['recall@5']:<5.2f} | "
            f"{metrics['precision@3']:<5.2f} | {metrics['precision@5']:<5.2f} | {rr_str:<5} | {latency_ms:>5.1f}ms"
        )

    print("=" * 95)

    # ── Aggregate Metrics ──
    non_empty_results = [r for r in results if not r["is_empty_gt"]]
    empty_results = [r for r in results if r["is_empty_gt"]]

    avg_recall_3 = sum(r["recall@3"] for r in non_empty_results) / len(non_empty_results)
    avg_recall_5 = sum(r["recall@5"] for r in non_empty_results) / len(non_empty_results)
    avg_precision_3 = sum(r["precision@3"] for r in non_empty_results) / len(non_empty_results)
    avg_precision_5 = sum(r["precision@5"] for r in non_empty_results) / len(non_empty_results)

    valid_rr = [r["reciprocal_rank"] for r in non_empty_results if r["reciprocal_rank"] is not None]
    mrr = sum(valid_rr) / len(valid_rr) if valid_rr else 0.0

    total_missed = sum(r["missed"] for r in non_empty_results)
    empty_correctness = sum(1 for r in empty_results if r["retrieved_count"] == 0) / len(empty_results)
    avg_latency = sum(latencies) / len(latencies)

    print("\n--- BASELINE RETRIEVAL AGGREGATE SUMMARY ---")
    print(f"Total Benchmark Queries:          {len(results)}")
    print(f"  - Non-empty Ground Truth:       {len(non_empty_results)}")
    print(f"  - Zero Ground Truth (Negative): {len(empty_results)}")
    print(f"Recall@3:                         {avg_recall_3:.4f}")
    print(f"Recall@5:                         {avg_recall_5:.4f}")
    print(f"Precision@3:                      {avg_precision_3:.4f}")
    print(f"Precision@5:                      {avg_precision_5:.4f}")
    print(f"Mean Reciprocal Rank (MRR):       {mrr:.4f}")
    print(f"Total Relevant Memories Missed:   {total_missed}")
    print(f"Cross-Project Leakages:           {cross_project_leaks}")
    print(f"Empty-Result Correctness:         {empty_correctness * 100:.1f}%")
    print(f"Average Retrieval Latency:        {avg_latency:.2f} ms")
    print("--------------------------------------------\n")

    # Invariants that current lexical search must satisfy:
    assert cross_project_leaks == 0, f"Critical security failure: {cross_project_leaks} cross-project leaks detected!"
    assert empty_correctness == 1.0, "Zero-ground-truth queries must return empty results"

    # Confirms known lexical search limitation: Paraphrases fail (Recall < 0.40)
    assert avg_recall_5 < 0.40, f"Expected baseline lexical search to fail on paraphrases, but got Recall@5={avg_recall_5}"
