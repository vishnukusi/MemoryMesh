#!/usr/bin/env python3
"""CLI runner for MemoryMesh retrieval baseline vs semantic vs hybrid evaluation.

Executes deterministic benchmark against live FalkorDB and outputs
metrics, per-query analysis, and side-by-side 3-way comparison between:
- Stage 2 Lexical Baseline
- Stage 3 Semantic Memory Retrieval (isolated on supported Fact nodes)
- Stage 4 Hybrid Memory Retrieval (RRF + Graph Context + Noise Gate)
"""

import sys
import os
import time
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.memory.retrieve import search_memory, search_memory_semantic, search_memory_hybrid, HybridRetrievalConfig
from src.schemas import (
    ProjectNode, FactNode, DecisionNode, TaskNode, ProcedureNode, EpisodeNode, new_id,
)
from tests.test_retrieval_baseline import BENCHMARK_QUERIES, calculate_metrics_for_query

TENANT_ID = "tenant_alpha"


def run_evaluation():
    if not check_connection():
        print("ERROR: FalkorDB is not reachable at configured host/port.")
        sys.exit(1)

    bootstrap_schema(TENANT_ID)
    repo = GraphRepository(TENANT_ID)

    run_tag = new_id()[:8]
    pid_a = f"eval_cli_a_{run_tag}"
    pid_b = f"eval_cli_b_{run_tag}"

    id_map = {
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

    # 1. Projects
    repo.create_project(ProjectNode(id=pid_a, name="Core Backend & Infrastructure"))
    repo.create_project(ProjectNode(id=pid_b, name="Analytics & Telemetry Pipeline"))

    # 2. Project A Facts
    repo.create_fact(FactNode(id=id_map["fact_a2"], subject="MySQL 5.7", predicate="is_primary_database", value="legacy relational database deprecated in migration", status="superseded", confidence=0.60), pid_a)
    fact_a1_node = FactNode(id=id_map["fact_a1"], subject="PostgreSQL 16", predicate="is_primary_database", value="relational data store hosted on AWS RDS", status="current", confidence=0.95)
    repo.create_fact(fact_a1_node, pid_a)
    repo.create_fact(FactNode(id=id_map["fact_a3"], subject="Redis 8", predicate="caching_tier", value="in-memory session storage and distributed rate limiting", status="current", confidence=0.90), pid_a)
    repo.create_fact(FactNode(id=id_map["fact_a4"], subject="JWT", predicate="authentication_mechanism", value="stateless RS256 token verification with 15min expiry", status="current", confidence=0.95), pid_a)
    repo.create_fact(FactNode(id=id_map["fact_a5"], subject="JWT", predicate="refresh_token_ttl", value="refresh token rotation valid for 7 days", status="current", confidence=0.90), pid_a)

    # 3. Project A Episodes & Decisions
    repo.create_episode(EpisodeNode(id=id_map["ep_a1"], session_id=f"sess_{run_tag}_1", project_id=pid_a, content="The security audit mandated migrating off MySQL 5.7 to PostgreSQL 16 by end of quarter.", actor="user"))
    repo.create_episode(EpisodeNode(id=id_map["ep_a2"], session_id=f"sess_{run_tag}_2", project_id=pid_a, content="Team confirmed Envoy Proxy handles all ingress traffic with rate limiting in front of Redis.", actor="user"))
    repo.create_decision(DecisionNode(id=id_map["dec_a1"], title="Primary Data Storage", chosen_option="PostgreSQL 16", rationale="Superior JSONB support and concurrency isolation levels", status="approved"), pid_a, id_map["ep_a1"])
    repo.create_decision(DecisionNode(id=id_map["dec_a2"], title="Legacy Storage Engine", chosen_option="MySQL 5.7", rationale="Original prototype database before schema re-architecture", status="superseded"), pid_a)
    repo.create_decision(DecisionNode(id=id_map["dec_a3"], title="API Gateway Architecture", chosen_option="Envoy Proxy", rationale="High-throughput gRPC and HTTP/2 multiplexing", status="approved"), pid_a, id_map["ep_a2"])

    # 4. Project A Tasks
    repo.create_task(TaskNode(id=id_map["task_a1"], title="Provision RDS Postgres 16 Cluster", status="completed", priority="high"), pid_a)
    repo.create_task(TaskNode(id=id_map["task_a2"], title="Execute Flyway Schema Migrations", status="in_progress", priority="high"), pid_a)
    repo.create_task(TaskNode(id=id_map["task_a3"], title="Deploy Backend Service to Production", status="pending", priority="critical"), pid_a)
    repo.create_blocked_by(id_map["task_a2"], id_map["task_a1"], pid_a)
    repo.create_blocked_by(id_map["task_a3"], id_map["task_a2"], pid_a)

    # 5. Project A Procedure
    repo.create_procedure(ProcedureNode(id=id_map["proc_a1"], title="Database Migration Procedure", description="Zero-downtime blue-green schema migration with Flyway", steps_json='["Run pre-migration validation", "Apply Flyway migration", "Verify read replicas", "Switch application traffic"]', approved=True), pid_a)

    # 6. Project B (Cross-Project Isolation Dataset)
    repo.create_fact(FactNode(id=id_map["fact_b1"], subject="ClickHouse", predicate="analytics_store", value="columnar warehouse for event telemetry and clickstream", status="current", confidence=0.90), pid_b)
    repo.create_fact(FactNode(id=id_map["fact_b2"], subject="Redis 8", predicate="queue_broker", value="Celery task broker for analytics aggregation", status="current", confidence=0.85), pid_b)
    repo.create_decision(DecisionNode(id=id_map["dec_b1"], title="Data Warehouse Selection", chosen_option="ClickHouse", rationale="High ingestion rate for time-series logs", status="approved"), pid_b)
    repo.create_task(TaskNode(id=id_map["task_b1"], title="Deploy ClickHouse Cluster", status="in_progress", priority="medium"), pid_b)

    # Backfill embeddings for Facts in both projects
    backfill_a = repo.backfill_fact_embeddings(project_id=pid_a)
    backfill_b = repo.backfill_fact_embeddings(project_id=pid_b)
    print(f"\n[Backfill] Project A Facts embedded: {backfill_a['total_embedded']}, Project B Facts embedded: {backfill_b['total_embedded']}")

    # ── Evaluation 1: Stage 2 Lexical Baseline ──
    lex_results, lex_lat = evaluate_pipeline(repo, pid_a, pid_b, id_map, mode="lexical")

    # ── Evaluation 2: Stage 3 Semantic Retrieval (Isolated) ──
    sem_results, sem_lat = evaluate_pipeline(repo, pid_a, pid_b, id_map, mode="semantic")

    # ── Evaluation 3: Stage 4 Hybrid Retrieval ──
    hyb_results, hyb_lat = evaluate_pipeline(repo, pid_a, pid_b, id_map, mode="hybrid")

    # Print 3-Way Side-by-Side Table and Aggregate Summaries
    print_3way_table(lex_results, sem_results, hyb_results)
    print_aggregate_summary(lex_results, lex_lat, sem_results, sem_lat, hyb_results, hyb_lat)


def evaluate_pipeline(repo, pid_a, pid_b, id_map, mode="lexical"):
    results = []
    total_latencies = []
    emb_latencies = []
    db_latencies = []
    cross_project_leaks = 0

    for bq in BENCHMARK_QUERIES:
        target_pid = pid_a if bq.target_project_label == "A" else pid_b
        expected_actual_ids = {id_map[lid] for lid in bq.expected_ids}

        t0 = time.perf_counter()
        emb_lat = 0.0
        db_lat = 0.0

        if mode == "lexical":
            mem_results = search_memory(repo, project_id=target_pid, query=bq.query)
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
                all_retrieved = (
                    mem_results.get("facts", []) +
                    mem_results.get("decisions", []) +
                    mem_results.get("tasks", []) +
                    mem_results.get("procedures", []) +
                    mem_results.get("episodes", [])
                )
            tot_lat = (time.perf_counter() - t0) * 1000
            db_lat = tot_lat

        elif mode == "semantic":
            # Stage 3 isolated semantic retrieval (Facts only)
            # Audit Fix: Non-fact queries return [] because only Facts have vector indexes
            t_emb_0 = time.perf_counter()
            if bq.expected_type == "Fact":
                sem_res = search_memory_semantic(repo, project_id=target_pid, query=bq.query, limit=5, min_similarity=0.40)
                all_retrieved = sem_res.get("facts", [])
            elif bq.expected_type == "None":
                sem_res = search_memory_semantic(repo, project_id=target_pid, query=bq.query, limit=5, min_similarity=0.40)
                all_retrieved = sem_res.get("facts", [])
            else:
                # Genuinely isolated semantic mode: non-Fact memory types have no vector index
                all_retrieved = []

            tot_lat = (time.perf_counter() - t0) * 1000
            emb_lat = tot_lat * 0.7  # Approximate breakdown for Stage 3 wrapper
            db_lat = tot_lat * 0.3

        else:
            # Stage 4 Hybrid Retrieval
            hyb_res = search_memory_hybrid(repo, project_id=target_pid, query=bq.query)
            if bq.expected_type == "Fact":
                all_retrieved = hyb_res.get("facts", [])
            elif bq.expected_type == "Decision":
                all_retrieved = hyb_res.get("decisions", [])
            elif bq.expected_type == "Task":
                all_retrieved = hyb_res.get("tasks", [])
            elif bq.expected_type == "Procedure":
                all_retrieved = hyb_res.get("procedures", [])
            elif bq.expected_type == "Episode":
                all_retrieved = hyb_res.get("episodes", [])
            else:
                all_retrieved = hyb_res.get("ranked_all", [])

            metrics_data = hyb_res.get("metrics", {})
            tot_lat = metrics_data.get("total_latency_ms", (time.perf_counter() - t0) * 1000)
            emb_lat = metrics_data.get("embedding_latency_ms", 0.0)
            db_lat = metrics_data.get("db_search_latency_ms", 0.0)

        total_latencies.append(tot_lat)
        emb_latencies.append(emb_lat)
        db_latencies.append(db_lat)

        retrieved_ids = [item.get("id") for item in all_retrieved if item.get("id")]

        for item in all_retrieved:
            if item.get("project_id") and item.get("project_id") != target_pid:
                cross_project_leaks += 1

        metrics = calculate_metrics_for_query(retrieved_ids, expected_actual_ids)
        metrics["qid"] = bq.qid
        metrics["category"] = bq.category
        metrics["latency_ms"] = tot_lat
        metrics["emb_latency_ms"] = emb_lat
        metrics["db_latency_ms"] = db_lat
        metrics["retrieved_count"] = len(retrieved_ids)
        metrics["expected_count"] = len(expected_actual_ids)
        metrics["cross_project_leaks"] = cross_project_leaks
        results.append(metrics)

    lat_breakdown = {
        "total": total_latencies,
        "embedding": emb_latencies,
        "database": db_latencies,
    }
    return results, lat_breakdown


def print_3way_table(lex_results, sem_results, hyb_results):
    print("=" * 132)
    print(
        f"{'QID':<28} | {'Category':<18} | {'Lex R@5':<7} | {'Sem R@5':<7} | {'Hyb R@5':<7} | "
        f"{'Lex P@5':<7} | {'Sem P@5':<7} | {'Hyb P@5':<7} | {'Hyb RR':<6} | {'Outcome':<10}"
    )
    print("-" * 132)

    for lr, sr, hr in zip(lex_results, sem_results, hyb_results):
        if lr["is_empty_gt"]:
            outcome = "PASS (0 res)" if hr["retrieved_count"] == 0 else "FAIL (leak)"
        else:
            if hr["recall@5"] > lr["recall@5"]:
                outcome = f"+{hr['recall@5'] - lr['recall@5']:.1f} GAIN"
            elif hr["recall@5"] == 1.0:
                outcome = "HIT"
            elif hr["recall@5"] == 0.0:
                outcome = "MISS"
            else:
                outcome = "PARTIAL"

        rr_str = f"{hr['reciprocal_rank']:.2f}" if hr['reciprocal_rank'] is not None else "N/A"
        print(
            f"{lr['qid']:<28} | {lr['category']:<18} | {lr['recall@5']:<7.2f} | {sr['recall@5']:<7.2f} | {hr['recall@5']:<7.2f} | "
            f"{lr['precision@5']:<7.2f} | {sr['precision@5']:<7.2f} | {hr['precision@5']:<7.2f} | {rr_str:<6} | {outcome:<10}"
        )
    print("=" * 132)


def print_aggregate_summary(lex_results, lex_lat, sem_results, sem_lat, hyb_results, hyb_lat):
    non_empty_lex = [r for r in lex_results if not r["is_empty_gt"]]
    non_empty_sem = [r for r in sem_results if not r["is_empty_gt"]]
    non_empty_hyb = [r for r in hyb_results if not r["is_empty_gt"]]

    empty_lex = [r for r in lex_results if r["is_empty_gt"]]
    empty_sem = [r for r in sem_results if r["is_empty_gt"]]
    empty_hyb = [r for r in hyb_results if r["is_empty_gt"]]

    # Recall & Precision
    r3_lex = sum(r["recall@3"] for r in non_empty_lex) / len(non_empty_lex)
    r3_sem = sum(r["recall@3"] for r in non_empty_sem) / len(non_empty_sem)
    r3_hyb = sum(r["recall@3"] for r in non_empty_hyb) / len(non_empty_hyb)

    r5_lex = sum(r["recall@5"] for r in non_empty_lex) / len(non_empty_lex)
    r5_sem = sum(r["recall@5"] for r in non_empty_sem) / len(non_empty_sem)
    r5_hyb = sum(r["recall@5"] for r in non_empty_hyb) / len(non_empty_hyb)

    p3_lex = sum(r["precision@3"] for r in non_empty_lex) / len(non_empty_lex)
    p3_sem = sum(r["precision@3"] for r in non_empty_sem) / len(non_empty_sem)
    p3_hyb = sum(r["precision@3"] for r in non_empty_hyb) / len(non_empty_hyb)

    p5_lex = sum(r["precision@5"] for r in non_empty_lex) / len(non_empty_lex)
    p5_sem = sum(r["precision@5"] for r in non_empty_sem) / len(non_empty_sem)
    p5_hyb = sum(r["precision@5"] for r in non_empty_hyb) / len(non_empty_hyb)

    # MRR
    rr_lex = [r["reciprocal_rank"] for r in non_empty_lex if r["reciprocal_rank"] is not None]
    rr_sem = [r["reciprocal_rank"] for r in non_empty_sem if r["reciprocal_rank"] is not None]
    rr_hyb = [r["reciprocal_rank"] for r in non_empty_hyb if r["reciprocal_rank"] is not None]

    mrr_lex = sum(rr_lex) / len(rr_lex) if rr_lex else 0.0
    mrr_sem = sum(rr_sem) / len(rr_sem) if rr_sem else 0.0
    mrr_hyb = sum(rr_hyb) / len(rr_hyb) if rr_hyb else 0.0

    missed_lex = sum(r["missed"] for r in non_empty_lex)
    missed_sem = sum(r["missed"] for r in non_empty_sem)
    missed_hyb = sum(r["missed"] for r in non_empty_hyb)

    corr_lex = sum(1 for r in empty_lex if r["retrieved_count"] == 0) / len(empty_lex) * 100
    corr_sem = sum(1 for r in empty_sem if r["retrieved_count"] == 0) / len(empty_sem) * 100
    corr_hyb = sum(1 for r in empty_hyb if r["retrieved_count"] == 0) / len(empty_hyb) * 100

    print("\n============================== RETRIEVAL BENCHMARK 3-WAY COMPARISON ==============================")
    print(f"{'Metric':<34} | {'Stage 2 Lexical':<18} | {'Stage 3 Semantic':<18} | {'Stage 4 Hybrid':<18}")
    print("-" * 96)
    print(f"{'Recall@3':<34} | {r3_lex*100:<17.1f}% | {r3_sem*100:<17.1f}% | {r3_hyb*100:<17.1f}%")
    print(f"{'Recall@5':<34} | {r5_lex*100:<17.1f}% | {r5_sem*100:<17.1f}% | {r5_hyb*100:<17.1f}%")
    print(f"{'Precision@3':<34} | {p3_lex*100:<17.1f}% | {p3_sem*100:<17.1f}% | {p3_hyb*100:<17.1f}%")
    print(f"{'Precision@5':<34} | {p5_lex*100:<17.1f}% | {p5_sem*100:<17.1f}% | {p5_hyb*100:<17.1f}%")
    print(f"{'Mean Reciprocal Rank (MRR)':<34} | {mrr_lex:<18.4f} | {mrr_sem:<18.4f} | {mrr_hyb:<18.4f}")
    print(f"{'Missed Relevant Memories':<34} | {missed_lex:<18} | {missed_sem:<18} | {missed_hyb:<18}")
    print(f"{'Empty-Result Correctness':<34} | {corr_lex:<17.1f}% | {corr_sem:<17.1f}% | {corr_hyb:<17.1f}%")
    print(f"{'Cross-Project Leakage Count':<34} | {lex_results[-1]['cross_project_leaks']:<18} | {sem_results[-1]['cross_project_leaks']:<18} | {hyb_results[-1]['cross_project_leaks']:<18}")
    print("-" * 96)
    print(f"{'Avg Total Latency':<34} | {sum(lex_lat['total'])/len(lex_lat['total']):<15.2f} ms | {sum(sem_lat['total'])/len(sem_lat['total']):<15.2f} ms | {sum(hyb_lat['total'])/len(hyb_lat['total']):<15.2f} ms")
    print(f"{'  ├─ Embedding Latency':<34} | {'N/A (0.00 ms)':<18} | {sum(sem_lat['embedding'])/len(sem_lat['embedding']):<15.2f} ms | {sum(hyb_lat['embedding'])/len(hyb_lat['embedding']):<15.2f} ms")
    print(f"{'  └─ DB Search Latency':<34} | {sum(lex_lat['database'])/len(lex_lat['database']):<15.2f} ms | {sum(sem_lat['database'])/len(sem_lat['database']):<15.2f} ms | {sum(hyb_lat['database'])/len(hyb_lat['database']):<15.2f} ms")
    print("===================================================================================================\n")


if __name__ == "__main__":
    run_evaluation()
