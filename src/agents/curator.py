"""Memory Curator Agent — extracts structured data from user messages.

Identifies candidate entities, facts, decisions, tasks, deadlines,
and procedures from natural language. Validates through Pydantic
before any database writes.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Optional

from src.db.repository import GraphRepository
from src.schemas import (
    ExtractionResult, ExtractedFact, ExtractedDecision, ExtractedTask,
    EpisodeNode, FactNode, DecisionNode, TaskNode, ProcedureNode,
    FactStatus, TaskStatus, AgentRunNode, EvidenceRef, new_id,
)
from src.services.model_service import generate_json

logger = logging.getLogger(__name__)

CURATOR_SYSTEM_PROMPT = """You are the Memory Curator for MemoryMesh, a project coordination system.

Your job: Extract structured information from user messages about their project.

RULES:
- Extract ONLY what the user explicitly states. Do not invent facts.
- Mark uncertain extractions with low confidence (0.3-0.5).
- Use the exact words/names the user provides.
- If the user mentions a deadline, extract it as a fact.
- If the user mentions a choice/selection with reasoning, extract it as a decision.
- If the user mentions work items, extract them as tasks.
- If the user describes a process/checklist, extract it as a procedure.
- If the user says task X depends on/is blocked by task Y, note blocked_by.

Return a JSON object with this exact structure:
{
  "entities": [{"name": "...", "entity_type": "person|tool|service|concept", "properties": {}}],
  "facts": [{"subject": "...", "predicate": "...", "value": "...", "confidence": 0.8}],
  "decisions": [{"title": "...", "chosen_option": "...", "rationale": "..."}],
  "tasks": [{"title": "...", "status": "pending|in_progress|blocked|completed", "description": "...", "blocked_by": ["task title"]}],
  "procedures": [{"title": "...", "description": "...", "steps": ["step1", "step2"]}],
  "task_updates": [{"title": "...", "new_status": "...", "reason": "..."}]
}

Only include sections that have data. Empty arrays are fine.
Do NOT wrap in markdown. Return raw JSON only."""


async def extract_from_message(
    message: str,
    project_context: str = "",
    existing_tasks: list[dict] = None,
) -> ExtractionResult:
    """Extract structured information from a user message using the LLM.

    Args:
        message: The user's natural language message.
        project_context: Summary of existing project state.
        existing_tasks: Currently known tasks for matching updates.

    Returns:
        Validated ExtractionResult (may be empty if parsing fails).
    """
    context_block = ""
    if project_context:
        context_block += f"\nCurrent project context:\n{project_context}\n"
    if existing_tasks:
        task_list = "\n".join(
            f"- {t.get('title', '?')} (status: {t.get('status', '?')}, id: {t.get('id', '?')})"
            for t in existing_tasks
        )
        context_block += f"\nExisting tasks:\n{task_list}\n"

    user_prompt = f"""Extract structured information from this project message:

"{message}"
{context_block}
Return the JSON extraction result."""

    try:
        result = await generate_json(CURATOR_SYSTEM_PROMPT, user_prompt)
        if result is None:
            logger.warning("Curator: LLM returned unparseable output")
            return ExtractionResult()
        return ExtractionResult.model_validate(result)
    except Exception as e:
        logger.error(f"Curator extraction failed: {e}")
        return ExtractionResult()


async def process_extraction(
    repo: GraphRepository,
    extraction: ExtractionResult,
    project_id: str,
    episode_id: str,
) -> dict:
    """Persist validated extractions to FalkorDB.

    Returns summary of what was created/updated.
    """
    created = {"facts": [], "decisions": [], "tasks": [], "procedures": []}

    # Create facts
    for ef in extraction.facts:
        fact = FactNode(
            subject=ef.subject,
            predicate=ef.predicate,
            value=ef.value,
            confidence=ef.confidence,
            project_id=project_id,
            status=FactStatus.CURRENT.value if ef.confidence >= 0.6 else FactStatus.CANDIDATE.value,
        )
        # Check for existing facts on the same subject+predicate in this project
        existing = repo.search_facts(ef.subject, project_id=project_id, limit=10)
        superseded = False
        is_duplicate = False

        for ex in existing:
            if (ex.get("predicate", "").lower() == ef.predicate.lower()
                    and ex.get("status") == "current"):
                if ex.get("value", "").strip().lower() == ef.value.strip().lower():
                    # Exact duplicate already exists in this project
                    is_duplicate = True
                    created["facts"].append({
                        "id": ex.get("id"),
                        "subject": ef.subject,
                        "value": ef.value,
                        "status": "duplicate_skipped",
                    })
                    break
                else:
                    repo.supersede_fact(ex["id"], fact, project_id, episode_id)
                    superseded = True
                    created["facts"].append({
                        "id": fact.id,
                        "subject": ef.subject,
                        "value": ef.value,
                        "status": "superseded_old",
                    })
                    break

        if not is_duplicate and not superseded:
            repo.create_fact(fact, project_id, episode_id)
            created["facts"].append({
                "id": fact.id,
                "subject": ef.subject,
                "value": ef.value,
                "status": "created",
            })

    # Create decisions
    for ed in extraction.decisions:
        decision = DecisionNode(
            title=ed.title,
            chosen_option=ed.chosen_option,
            rationale=ed.rationale,
            project_id=project_id,
        )
        repo.create_decision(decision, project_id, episode_id)
        created["decisions"].append({"id": decision.id, "title": ed.title})

    # Create or update tasks
    for et in extraction.tasks:
        # Check if task already exists in this project
        existing_tasks = repo.search_tasks(et.title, project_id=project_id)
        if existing_tasks:
            task_data = existing_tasks[0]
            # Only update if status changed
            if et.status != task_data.get("status"):
                try:
                    repo.update_task_status(
                        task_data["id"], et.status,
                        expected_revision=task_data.get("revision", 1),
                        enforce_lifecycle=True,
                    )
                    # Record the update as an episode
                    update_episode = EpisodeNode(
                        session_id="system",
                        project_id=project_id,
                        content=f"Task '{et.title}' status changed to {et.status}",
                        actor="curator",
                        event_type="task_update",
                        source_event_id=episode_id,
                    )
                    repo.create_episode(update_episode)
                except Exception as exc:
                    logger.warning(f"Curator could not update task status for '{et.title}': {exc}")
            created["tasks"].append({"id": task_data["id"], "title": et.title, "action": "updated"})
        else:
            task = TaskNode(
                title=et.title,
                description=et.description,
                status=et.status,
                project_id=project_id,
            )
            repo.create_task(task, project_id)
            created["tasks"].append({"id": task.id, "title": et.title, "action": "created"})

            # Handle blocked_by relationships
            if et.blocked_by:
                for blocker_title in et.blocked_by:
                    blockers = repo.search_tasks(blocker_title, project_id=project_id)
                    if blockers:
                        try:
                            repo.create_blocked_by(task.id, blockers[0]["id"])
                            # Also set task status to blocked if it has blockers
                            if task.status == "pending":
                                repo.update_task_status(task.id, "blocked", expected_revision=1, enforce_lifecycle=True)
                        except Exception as exc:
                            logger.warning(f"Could not link blocker '{blocker_title}' to task '{task.id}': {exc}")

    # Handle explicit task updates
    for tu in extraction.task_updates:
        title = tu.get("title", "")
        new_status = tu.get("new_status", "")
        if title and new_status:
            matches = repo.search_tasks(title, project_id=project_id)
            if matches:
                task_data = matches[0]
                try:
                    result = repo.update_task_status(
                        task_data["id"], new_status,
                        expected_revision=task_data.get("revision", 1),
                        enforce_lifecycle=True,
                    )
                    if result:
                        update_ep = EpisodeNode(
                            session_id="system",
                            project_id=project_id,
                            content=f"Task '{title}' updated to {new_status}. Reason: {tu.get('reason', 'user request')}",
                            actor="curator",
                            event_type="task_update",
                            source_event_id=episode_id,
                        )
                        repo.create_episode(update_ep)
                except Exception as exc:
                    logger.warning(f"Curator explicit task update failed for '{title}': {exc}")

    # Create procedures
    for ep in extraction.procedures:
        procedure = ProcedureNode(
            title=ep.title,
            description=ep.description,
            steps_json=json.dumps(ep.steps),
            project_id=project_id,
            approved=False,  # New procedures need approval
        )
        repo.create_procedure(procedure, project_id)
        created["procedures"].append({"id": procedure.id, "title": ep.title})

    return created
