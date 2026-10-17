"""Investigator / Recall Agent — retrieves relevant context from FalkorDB.

This agent is READ-ONLY. It never modifies tasks, decisions, or facts.
It searches the graph for information relevant to the user's question.
"""

from __future__ import annotations
import logging
from typing import Optional

from src.db.repository import GraphRepository
from src.schemas import InvestigationResult
from src.services.model_service import generate_json

logger = logging.getLogger(__name__)

INVESTIGATOR_SYSTEM_PROMPT = """You are the Investigator agent for MemoryMesh.

Your job: Given a user's question and retrieved graph records, produce a structured
summary of the most relevant information.

RULES:
- You are READ-ONLY. Never suggest modifying any record.
- Base your summary ONLY on the provided graph records.
- If information is missing, say so explicitly.
- Distinguish current facts from superseded/historical facts.
- When referencing a record, include its ID.
- For task dependency questions, trace the BLOCKED_BY chain.
- For decision questions, include the supporting episode evidence.

Return a JSON object:
{
  "relevant_facts": [{"id": "...", "subject": "...", "value": "...", "status": "..."}],
  "relevant_decisions": [{"id": "...", "title": "...", "chosen_option": "...", "rationale": "..."}],
  "relevant_tasks": [{"id": "...", "title": "...", "status": "...", "blockers": [...]}],
  "relevant_episodes": [{"id": "...", "content": "...", "timestamp": "..."}],
  "relevant_procedures": [{"id": "...", "title": "...", "steps": [...]}],
  "blockers": [{"blocked_task": "...", "blocker_task": "...", "blocker_status": "..."}],
  "summary": "A concise narrative answering the question based on evidence."
}

Return raw JSON only. No markdown."""


async def investigate(
    repo: GraphRepository,
    question: str,
    project_id: str,
) -> InvestigationResult:
    """Search FalkorDB for information relevant to the user's question.

    Performs multiple targeted queries and then asks the LLM to synthesize.
    """
    # Step 1: Gather raw data from graph queries
    context_parts = []

    # Search facts scoped to project
    facts = repo.search_facts(question, project_id=project_id, limit=10)
    # Also get all project facts for context
    project_facts = repo.get_facts_by_project(project_id)
    all_facts = {f.get("id"): f for f in project_facts}
    for f in facts:
        all_facts[f.get("id")] = f
    # Prioritize current facts over superseded facts
    fact_list = sorted(
        all_facts.values(),
        key=lambda f: (1 if f.get("status") == "current" else 0, float(f.get("confidence", 0))),
        reverse=True,
    )

    if fact_list:
        context_parts.append("FACTS:\n" + "\n".join(
            f"- [{f.get('id', '?')}] {f.get('subject', '?')} {f.get('predicate', '?')} "
            f"{f.get('value', '?')} (status: {f.get('status', '?')})"
            for f in fact_list
        ))

    # Search decisions scoped to project
    decisions = repo.search_decisions(question, project_id=project_id, limit=10)
    project_decisions = repo.get_decisions_by_project(project_id)
    all_decisions = {d.get("id"): d for d in project_decisions}
    for d in decisions:
        all_decisions[d.get("id")] = d
    decision_list = list(all_decisions.values())

    if decision_list:
        context_parts.append("DECISIONS:\n" + "\n".join(
            f"- [{d.get('id', '?')}] {d.get('title', '?')}: chose {d.get('chosen_option', '?')} "
            f"because {d.get('rationale', 'no rationale recorded')}"
            for d in decision_list
        ))

    # Get tasks and their dependencies
    tasks = repo.get_tasks_by_project(project_id)
    task_info = []
    for t in tasks:
        blockers = repo.get_task_blockers(t.get("id", ""))
        blocker_names = [b.get("title", "?") + f" (status: {b.get('status', '?')})" for b in blockers]
        info = {**t, "blockers": blocker_names}
        task_info.append(info)

    if task_info:
        context_parts.append("TASKS:\n" + "\n".join(
            f"- [{t.get('id', '?')}] {t.get('title', '?')} (status: {t.get('status', '?')}) "
            + (f"BLOCKED BY: {', '.join(t['blockers'])}" if t.get('blockers') else "")
            for t in task_info
        ))

    # Search episodes
    episodes = repo.search_episodes(project_id, question, limit=10)
    # Also get recent episodes
    recent = repo.get_episodes_by_project(project_id, limit=10)
    all_episodes = {e.get("id"): e for e in recent}
    for e in episodes:
        all_episodes[e.get("id")] = e
    episode_list = sorted(all_episodes.values(), key=lambda e: e.get("timestamp", ""), reverse=True)[:15]

    if episode_list:
        context_parts.append("EPISODES (conversation history):\n" + "\n".join(
            f"- [{e.get('id', '?')}] ({e.get('timestamp', '?')}) {e.get('actor', '?')}: "
            f"{e.get('content', '?')[:200]}"
            for e in episode_list
        ))

    # Get procedures scoped to project
    procedures = repo.search_procedures(question, project_id=project_id, limit=5)
    project_procs = repo.get_procedures_by_project(project_id)
    all_procs = {p.get("id"): p for p in project_procs}
    for p in procedures:
        all_procs[p.get("id")] = p

    if all_procs:
        context_parts.append("PROCEDURES:\n" + "\n".join(
            f"- [{p.get('id', '?')}] {p.get('title', '?')}: {p.get('description', '')}"
            + (f" (approved: {p.get('approved', False)})" if 'approved' in p else "")
            for p in all_procs.values()
        ))

    # Step 2: Ask LLM to synthesize
    graph_context = "\n\n".join(context_parts) if context_parts else "No relevant records found in the graph."

    user_prompt = f"""Question: "{question}"

Graph records retrieved from FalkorDB:

{graph_context}

Based ONLY on these graph records, provide a structured summary answering the question.
Include record IDs for traceability."""

    try:
        result = await generate_json(INVESTIGATOR_SYSTEM_PROMPT, user_prompt)
        if result:
            return InvestigationResult.model_validate(result)
    except Exception as e:
        logger.error(f"Investigator synthesis failed: {e}")

    # Fallback: return raw data without LLM synthesis
    return InvestigationResult(
        relevant_facts=fact_list[:5],
        relevant_decisions=decision_list[:5],
        relevant_tasks=task_info[:10],
        relevant_episodes=[{"id": e.get("id"), "content": e.get("content", "")[:200],
                            "timestamp": e.get("timestamp", "")} for e in episode_list[:5]],
        summary=f"Retrieved {len(fact_list)} facts, {len(decision_list)} decisions, "
                f"{len(task_info)} tasks, {len(episode_list)} episodes for query: '{question}'",
    )
