"""Memory retrieval — handles querying stored memories."""

from __future__ import annotations
from src.db.repository import GraphRepository


def retrieve_session_history(repo: GraphRepository, session_id: str) -> list[dict]:
    """Retrieve all episodes from a specific session."""
    return repo.get_episodes_by_session(session_id)


def retrieve_project_memory(repo: GraphRepository, project_id: str) -> dict:
    """Retrieve comprehensive project memory including facts, decisions, tasks."""
    return {
        "facts": repo.get_facts_by_project(project_id),
        "decisions": repo.get_decisions_by_project(project_id),
        "tasks": repo.get_tasks_by_project(project_id),
        "procedures": repo.get_procedures_by_project(project_id),
        "recent_episodes": repo.get_episodes_by_project(project_id, limit=20),
    }


def search_memory(repo: GraphRepository, project_id: str, query: str) -> dict:
    """Search across all memory types, scoped to the specified project."""
    return {
        "facts": repo.search_facts(query, project_id=project_id, limit=10),
        "decisions": repo.search_decisions(query, project_id=project_id, limit=10),
        "tasks": repo.search_tasks(query, project_id=project_id),
        "episodes": repo.search_episodes(project_id, query, limit=10),
        "procedures": repo.search_procedures(query, project_id=project_id, limit=5),
    }


def search_memory_semantic(
    repo: GraphRepository,
    project_id: str,
    query: str,
    limit: int = 5,
    min_similarity: float = 0.40,
) -> dict:
    """Perform semantic retrieval across memories using vector similarity.

    In Stage 3, implements semantic retrieval for Facts with safe fallback:
    - If embedding generation or vector search fails, reports failure and falls
      back to lexical fact search without crashing.
    - Preserves existing lexical retrieval for other memory types.
    """
    from src.services.embedding_service import generate_embedding_safe, format_query_for_embedding

    formatted_query = format_query_for_embedding(query)
    if not formatted_query:
        return {
            "facts": [],
            "query_embedding_generated": False,
            "fallback_used": False,
            "error": "Empty query",
        }

    query_vec, emb_err = generate_embedding_safe(formatted_query)
    if query_vec is None:
        lexical_facts = repo.search_facts(query, project_id=project_id, limit=limit)
        return {
            "facts": lexical_facts,
            "query_embedding_generated": False,
            "fallback_used": True,
            "error": emb_err or "Embedding generation failed",
        }

    try:
        facts = repo.search_facts_semantic(
            query_vector=query_vec,
            project_id=project_id,
            limit=limit,
            min_similarity=min_similarity,
        )
        return {
            "facts": facts,
            "query_embedding_generated": True,
            "fallback_used": False,
            "error": None,
        }
    except Exception as e:
        lexical_facts = repo.search_facts(query, project_id=project_id, limit=limit)
        return {
            "facts": lexical_facts,
            "query_embedding_generated": True,
            "fallback_used": True,
            "error": f"Vector search error: {e}",
        }


# ─── Stage 4: Hybrid Memory Retrieval ─────────────────────────────

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import time
import re

HISTORICAL_STEMS = {
    "migrat", "history", "histor", "legacy", "supersed", "previous",
    "prior", "former", "deprecat", "why did we change", "initial", "original", "old"
}

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "what", "which", "who", "how",
    "does", "did", "our", "we", "me", "tell", "about", "why"
}


@dataclass
class HybridRetrievalConfig:
    """Configurable parameters for Reciprocal Rank Fusion and Graph Context scoring."""
    k_rrf: int = 60
    weight_lexical: float = 1.0
    weight_semantic: float = 1.2
    status_boost_current: float = 0.05
    status_penalty_superseded: float = 0.10
    provenance_boost: float = 0.03
    min_semantic_similarity: float = 0.58
    min_lexical_coverage: float = 0.35
    min_rrf_threshold: float = 0.005
    limit_per_type: int = 5
    limit_total: int = 15


def is_historical_query(query: str) -> bool:
    """Detect whether query inquires into previous versions, deprecated systems, or migration history."""
    q_lower = query.lower()
    return any(stem in q_lower for stem in HISTORICAL_STEMS)


def get_content_words(text: str) -> list[str]:
    """Tokenize and filter stop words from a string."""
    words = re.findall(r"[a-zA-Z0-9_\-\.]+", text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def extract_query_terms(query: str) -> list[str]:
    """Extract full query, multi-word n-grams, and significant terms for lexical indexing."""
    terms = [query.strip()]
    c_words = get_content_words(query)
    for n in (3, 2):
        for i in range(len(c_words) - n + 1):
            phrase = " ".join(c_words[i:i+n])
            if phrase not in terms:
                terms.append(phrase)
    for w in c_words:
        if len(w) >= 4 and w not in terms:
            terms.append(w)
    return terms


def word_matches_text(word: str, text_words: list[str]) -> bool:
    """Stem/prefix match between a query word and target text words."""
    if word in text_words:
        return True
    w_stem = word[:5] if len(word) >= 5 else word[:4]
    return any(tw.startswith(w_stem) or w_stem.startswith(tw[:4]) for tw in text_words if len(tw) >= 4)


def calculate_text_coverage(query_words: list[str], target_text: str) -> float:
    """Compute fraction of query content words covered by candidate text."""
    if not query_words:
        return 0.0
    text_words = re.findall(r"[a-zA-Z0-9_\-\.]+", target_text.lower())
    matched = sum(1 for w in query_words if word_matches_text(w, text_words))
    return matched / len(query_words)


def search_memory_hybrid(
    repo: GraphRepository,
    project_id: str,
    query: str,
    config: Optional[HybridRetrievalConfig] = None,
) -> dict:
    """Perform hybrid memory retrieval combining lexical, semantic, and graph context.

    Ranking:
    - Base score: Reciprocal Rank Fusion (RRF) across lexical and semantic candidate lists.
    - Graph context:
      * Current vs superseded status weighting with automatic inversion for historical queries.
      * Provenance boost for decisions with supporting episodes, approved procedures, and high-confidence facts.
      * Task dependency expansion via BLOCKED_BY relationships.
    - Project Isolation:
      * 100% scoped to authorized project_id; cross-project memories are strictly excluded.
      * Relies on native vector index + in-project scan fallback.
    - Evidence Quality:
      * Pure semantic candidates must pass min_semantic_similarity to reject out-of-domain noise.
      * Multi-word lexical candidates must pass min_lexical_coverage to reject coincidental single-word hits.
      * Returns empty results when no relevant candidate passes relevance criteria.
    """
    t_start = time.perf_counter()
    if config is None:
        config = HybridRetrievalConfig()

    empty_metrics = {
        "embedding_latency_ms": 0.0,
        "db_search_latency_ms": 0.0,
        "total_latency_ms": 0.0,
        "query_embedding_generated": False,
        "semantic_fallback_used": False,
        "is_historical_query": False,
        "candidate_counts": {"lexical": 0, "semantic": 0, "fused": 0},
    }

    if not project_id or not project_id.strip() or not query or not query.strip():
        return {
            "facts": [],
            "decisions": [],
            "tasks": [],
            "procedures": [],
            "episodes": [],
            "ranked_all": [],
            "metrics": empty_metrics,
        }

    terms = extract_query_terms(query)
    q_words = get_content_words(query)
    is_hist = is_historical_query(query)

    t_db_start = time.perf_counter()

    # 1. Lexical retrieval across terms
    lex_facts: dict[str, dict] = {}
    lex_decisions: dict[str, dict] = {}
    lex_tasks: dict[str, dict] = {}
    lex_procedures: dict[str, dict] = {}
    lex_episodes: dict[str, dict] = {}

    for term in terms:
        # Facts
        for f in repo.search_facts(term, project_id=project_id, limit=10):
            fid = f.get("id")
            if fid and fid not in lex_facts:
                fact_text = f"{f.get('subject', '')} {f.get('predicate', '')} {f.get('value', '')}"
                cov = calculate_text_coverage(q_words, fact_text)
                if cov >= config.min_lexical_coverage:
                    f["_lex_rank"] = len(lex_facts)
                    f["_coverage"] = cov
                    lex_facts[fid] = f

        # Decisions
        for d in repo.search_decisions(term, project_id=project_id, limit=10):
            did = d.get("id")
            if did and did not in lex_decisions:
                ev = repo.get_decision_with_evidence(did)
                episodes = ev.get("supporting_episodes", []) if ev else []
                ep_texts = " ".join(e.get("content", "") for e in episodes)
                dec_text = f"{d.get('title', '')} {d.get('chosen_option', '')} {d.get('rationale', '')} {ep_texts}"
                cov = calculate_text_coverage(q_words, dec_text)
                if cov >= config.min_lexical_coverage:
                    d["_lex_rank"] = len(lex_decisions)
                    d["_coverage"] = cov
                    d["_supporting_episodes"] = episodes
                    lex_decisions[did] = d

        # Tasks
        for t in repo.search_tasks(term, project_id=project_id):
            tid = t.get("id")
            if tid and tid not in lex_tasks:
                task_text = f"{t.get('title', '')} {t.get('description', '')}"
                cov = calculate_text_coverage(q_words, task_text)
                if cov >= config.min_lexical_coverage:
                    t["_lex_rank"] = len(lex_tasks)
                    t["_coverage"] = cov
                    lex_tasks[tid] = t

                    # Graph context: retrieve task blockers (prerequisites)
                    blockers = repo.get_task_blockers(tid)
                    for b in blockers:
                        bid = b.get("id")
                        if bid and bid not in lex_tasks:
                            b["_lex_rank"] = len(lex_tasks) + 1
                            b["_is_blocker_context"] = True
                            b["_coverage"] = cov
                            lex_tasks[bid] = b

        # Procedures
        for p in repo.search_procedures(term, project_id=project_id, limit=5):
            pid = p.get("id")
            if pid and pid not in lex_procedures:
                proc_text = f"{p.get('title', '')} {p.get('description', '')}"
                cov = calculate_text_coverage(q_words, proc_text)
                if cov >= config.min_lexical_coverage:
                    p["_lex_rank"] = len(lex_procedures)
                    p["_coverage"] = cov
                    lex_procedures[pid] = p

        # Episodes
        for e in repo.search_episodes(project_id, term, limit=5):
            eid = e.get("id")
            if eid and eid not in lex_episodes:
                ep_text = e.get("content", "")
                cov = calculate_text_coverage(q_words, ep_text)
                if cov >= config.min_lexical_coverage:
                    e["_lex_rank"] = len(lex_episodes)
                    e["_coverage"] = cov
                    lex_episodes[eid] = e

    db_lex_latency_ms = (time.perf_counter() - t_db_start) * 1000

    # 2. Semantic retrieval on Facts
    from src.services.embedding_service import generate_embedding_safe, format_query_for_embedding

    t_emb_start = time.perf_counter()
    fmt_query = format_query_for_embedding(query)
    q_vec, emb_err = generate_embedding_safe(fmt_query)
    emb_latency_ms = (time.perf_counter() - t_emb_start) * 1000

    sem_facts: dict[str, dict] = {}
    t_sem_db_start = time.perf_counter()
    sem_fallback_used = False

    if q_vec:
        try:
            raw_sem = repo.search_facts_semantic(
                query_vector=q_vec,
                project_id=project_id,
                limit=10,
                min_similarity=config.min_semantic_similarity,
            )
            for s_idx, sf in enumerate(raw_sem):
                fid = sf.get("id")
                if fid:
                    sf["_sem_rank"] = s_idx
                    sem_facts[fid] = sf
        except Exception:
            sem_fallback_used = True
    else:
        sem_fallback_used = True

    db_sem_latency_ms = (time.perf_counter() - t_sem_db_start) * 1000
    total_db_latency_ms = db_lex_latency_ms + db_sem_latency_ms

    # 3. Fuse & Score per memory type
    all_fused: list[dict] = []

    # Facts fusion
    fact_ids = set(lex_facts.keys()) | set(sem_facts.keys())
    for fid in fact_ids:
        in_lex = fid in lex_facts
        in_sem = fid in sem_facts
        node = dict(sem_facts[fid] if in_sem else lex_facts[fid])

        # Enforce project boundary
        if node.get("project_id") and node.get("project_id") != project_id:
            continue

        # Pure semantic match gate
        if in_sem and not in_lex:
            sim = float(node.get("similarity", 0.0) or 0.0)
            if sim < config.min_semantic_similarity:
                continue

        rrf_score = 0.0
        lex_rank = None
        sem_rank = None
        if in_lex:
            lex_rank = lex_facts[fid]["_lex_rank"]
            rrf_score += config.weight_lexical / (config.k_rrf + lex_rank + 1)
        if in_sem:
            sem_rank = sem_facts[fid]["_sem_rank"]
            rrf_score += config.weight_semantic / (config.k_rrf + sem_rank + 1)

        status = node.get("status", "current")
        if status in ("superseded", "deprecated"):
            delta_status = config.status_boost_current if is_hist else -config.status_penalty_superseded
        elif status in ("current", "approved", "completed"):
            delta_status = config.status_boost_current
        else:
            delta_status = 0.0

        conf = float(node.get("confidence", 1.0) or 1.0)
        delta_prov = config.provenance_boost * (conf - 0.5) if conf >= 0.8 else 0.0

        composite_score = rrf_score + delta_status + delta_prov
        if composite_score >= config.min_rrf_threshold:
            clean_node = {k: v for k, v in node.items() if not k.startswith("_")}
            clean_node["score"] = round(composite_score, 5)
            clean_node["rrf_score"] = round(rrf_score, 5)
            clean_node["lexical_rank"] = lex_rank
            clean_node["semantic_rank"] = sem_rank
            clean_node["memory_type"] = "fact"
            all_fused.append(clean_node)

    # Decisions
    for did, d in lex_decisions.items():
        if d.get("project_id") and d.get("project_id") != project_id:
            continue
        lex_rank = d["_lex_rank"]
        rrf_score = config.weight_lexical / (config.k_rrf + lex_rank + 1)
        status = d.get("status", "approved")
        if status in ("superseded", "deprecated"):
            delta_status = config.status_boost_current if is_hist else -config.status_penalty_superseded
        elif status in ("approved", "completed", "current"):
            delta_status = config.status_boost_current
        else:
            delta_status = 0.0

        supporting_eps = d.get("_supporting_episodes", [])
        delta_prov = config.provenance_boost if supporting_eps else 0.0

        composite_score = rrf_score + delta_status + delta_prov
        if composite_score >= config.min_rrf_threshold:
            clean_d = {k: v for k, v in d.items() if not k.startswith("_")}
            clean_d["score"] = round(composite_score, 5)
            clean_d["rrf_score"] = round(rrf_score, 5)
            clean_d["lexical_rank"] = lex_rank
            clean_d["semantic_rank"] = None
            clean_d["memory_type"] = "decision"
            clean_d["supporting_episodes"] = supporting_eps
            all_fused.append(clean_d)

    # Tasks
    for tid, t in lex_tasks.items():
        if t.get("project_id") and t.get("project_id") != project_id:
            continue
        lex_rank = t["_lex_rank"]
        rrf_score = config.weight_lexical / (config.k_rrf + lex_rank + 1)
        status = t.get("status", "in_progress")
        delta_status = config.status_boost_current if status in ("completed", "in_progress", "pending") else 0.0
        delta_prov = config.provenance_boost if t.get("priority") in ("critical", "high") or t.get("_is_blocker_context") else 0.0

        composite_score = rrf_score + delta_status + delta_prov
        if composite_score >= config.min_rrf_threshold:
            clean_t = {k: v for k, v in t.items() if not k.startswith("_")}
            clean_t["score"] = round(composite_score, 5)
            clean_t["rrf_score"] = round(rrf_score, 5)
            clean_t["lexical_rank"] = lex_rank
            clean_t["semantic_rank"] = None
            clean_t["memory_type"] = "task"
            clean_t["is_blocker_context"] = bool(t.get("_is_blocker_context", False))
            all_fused.append(clean_t)

    # Procedures
    for pid_val, p in lex_procedures.items():
        if p.get("project_id") and p.get("project_id") != project_id:
            continue
        lex_rank = p["_lex_rank"]
        rrf_score = config.weight_lexical / (config.k_rrf + lex_rank + 1)
        delta_status = config.status_boost_current if p.get("approved") else 0.0
        delta_prov = config.provenance_boost

        composite_score = rrf_score + delta_status + delta_prov
        if composite_score >= config.min_rrf_threshold:
            clean_p = {k: v for k, v in p.items() if not k.startswith("_")}
            clean_p["score"] = round(composite_score, 5)
            clean_p["rrf_score"] = round(rrf_score, 5)
            clean_p["lexical_rank"] = lex_rank
            clean_p["semantic_rank"] = None
            clean_p["memory_type"] = "procedure"
            all_fused.append(clean_p)

    # Episodes
    for eid, ep in lex_episodes.items():
        if ep.get("project_id") and ep.get("project_id") != project_id:
            continue
        lex_rank = ep["_lex_rank"]
        rrf_score = config.weight_lexical / (config.k_rrf + lex_rank + 1)
        composite_score = rrf_score

        if composite_score >= config.min_rrf_threshold:
            clean_e = {k: v for k, v in ep.items() if not k.startswith("_")}
            clean_e["score"] = round(composite_score, 5)
            clean_e["rrf_score"] = round(rrf_score, 5)
            clean_e["lexical_rank"] = lex_rank
            clean_e["semantic_rank"] = None
            clean_e["memory_type"] = "episode"
            all_fused.append(clean_e)

    # Global sort descending by score
    all_fused.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    # Categorize and limit
    facts = [x for x in all_fused if x["memory_type"] == "fact"][:config.limit_per_type]
    decisions = [x for x in all_fused if x["memory_type"] == "decision"][:config.limit_per_type]
    tasks = [x for x in all_fused if x["memory_type"] == "task"][:config.limit_per_type]
    procedures = [x for x in all_fused if x["memory_type"] == "procedure"][:config.limit_per_type]
    episodes = [x for x in all_fused if x["memory_type"] == "episode"][:config.limit_per_type]

    total_latency_ms = (time.perf_counter() - t_start) * 1000

    metrics = {
        "embedding_latency_ms": round(emb_latency_ms, 2),
        "db_search_latency_ms": round(total_db_latency_ms, 2),
        "total_latency_ms": round(total_latency_ms, 2),
        "query_embedding_generated": q_vec is not None,
        "semantic_fallback_used": sem_fallback_used,
        "is_historical_query": is_hist,
        "candidate_counts": {
            "lexical": len(lex_facts) + len(lex_decisions) + len(lex_tasks) + len(lex_procedures) + len(lex_episodes),
            "semantic": len(sem_facts),
            "fused": len(all_fused),
        },
    }

    return {
        "facts": facts,
        "decisions": decisions,
        "tasks": tasks,
        "procedures": procedures,
        "episodes": episodes,
        "ranked_all": all_fused[:config.limit_total],
        "metrics": metrics,
    }
