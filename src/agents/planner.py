"""Planner / Coordinator Agent — decides next actions using retrieved context.

Analyzes project state, recommends next steps, and creates
explicit handoffs when needed.
"""

from __future__ import annotations
import logging
from typing import Optional

from src.db.repository import GraphRepository
from src.schemas import (
    PlannerAction, HandoffNode, AgentRunNode,
    InvestigationResult, new_id,
)
from src.services.model_service import generate_json

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the Planner agent for MemoryMesh.

Your job: Given the user's request and the Investigator's findings, decide the best action.

RULES:
- Base recommendations on the retrieved graph data, not assumptions.
- Consider task dependencies, deadlines, and blocking relationships.
- Do NOT claim a task is completed unless it has confirmed 'completed' status.
- For task updates, specify the exact task to modify.
- For coordination requests, create a handoff to the appropriate agent.
- Explain your reasoning clearly.

Possible action_types:
- "none": Just provide information/recommendation, no state change needed.
- "update_task": Update a task's status (requires target_task_id, new_status).
- "create_handoff": Create a handoff to another agent (requires handoff_to).
- "recommend": Provide a recommendation about what to work on next.

Return JSON:
{
  "recommendation": "Your recommendation text",
  "action_type": "none|update_task|create_handoff|recommend",
  "target_task_id": "task-id or null",
  "new_status": "status or null",
  "handoff_to": "agent name or null",
  "reasoning": "Explanation of why this action"
}

Return raw JSON only."""


async def plan_action(
    repo: GraphRepository,
    user_request: str,
    investigation: InvestigationResult,
    project_id: str,
) -> PlannerAction:
    """Analyze context and decide next action."""

    # Build context from investigation
    context = f"Investigation summary: {investigation.summary}\n\n"

    if investigation.relevant_tasks:
        context += "Tasks:\n" + "\n".join(
            f"- {t.get('title', '?')} (status: {t.get('status', '?')}, id: {t.get('id', '?')})"
            + (f" blockers: {t.get('blockers', [])}" if t.get('blockers') else "")
            for t in investigation.relevant_tasks
        ) + "\n\n"

    if investigation.relevant_decisions:
        context += "Decisions:\n" + "\n".join(
            f"- {d.get('title', '?')}: {d.get('chosen_option', '?')}"
            for d in investigation.relevant_decisions
        ) + "\n\n"

    if investigation.blockers:
        context += "Blockers:\n" + "\n".join(
            f"- {b.get('blocked_task', '?')} blocked by {b.get('blocker_task', '?')} "
            f"(blocker status: {b.get('blocker_status', '?')})"
            for b in investigation.blockers
        ) + "\n\n"

    user_prompt = f"""User request: "{user_request}"

Retrieved context:
{context}

What action should be taken?"""

    try:
        result = await generate_json(PLANNER_SYSTEM_PROMPT, user_prompt)
        if result:
            return PlannerAction.model_validate(result)
    except Exception as e:
        logger.error(f"Planner failed: {e}")

    return PlannerAction(
        recommendation="Unable to determine action. Please provide more context.",
        action_type="none",
        reasoning="Planner could not generate a response.",
    )


async def execute_plan(
    repo: GraphRepository,
    plan: PlannerAction,
    project_id: str,
    run_id: str,
) -> dict:
    """Execute the planned action against FalkorDB.

    Returns dict describing what was done.
    """
    result = {"action": plan.action_type, "success": False, "details": {}}

    if plan.action_type == "update_task" and plan.target_task_id and plan.new_status:
        task = repo.get_task(plan.target_task_id)
        if task:
            if task.get("project_id") and task.get("project_id") != project_id:
                result["details"] = {"error": f"Task {plan.target_task_id} does not belong to project {project_id}"}
                return result
            try:
                updated = repo.update_task_status(
                    plan.target_task_id,
                    plan.new_status,
                    expected_revision=task.get("revision", 1),
                    enforce_lifecycle=True,
                )
                result["success"] = updated is not None
                result["details"] = {
                    "task_id": plan.target_task_id,
                    "old_status": task.get("status"),
                    "new_status": plan.new_status,
                }
            except Exception as e:
                logger.warning(f"Planner could not execute task status update: {e}")
                result["success"] = False
                result["details"] = {"error": str(e)}
        else:
            result["details"] = {"error": f"Task {plan.target_task_id} not found"}

    elif plan.action_type == "create_handoff" and plan.handoff_to:
        allowed_roles = {"curator", "investigator", "planner", "verifier"}
        target_role = plan.handoff_to.lower().strip()
        if target_role not in allowed_roles:
            result["details"] = {"error": f"Invalid handoff target '{plan.handoff_to}'. Allowed: {sorted(list(allowed_roles))}"}
            return result

        handoff = HandoffNode(
            from_agent="planner",
            to_agent=target_role,
            task_id=plan.target_task_id or "",
            context_summary=plan.recommendation,
        )
        created = repo.create_handoff(handoff)
        if created:
            repo.link_run_to_handoff(run_id, handoff.id)
            result["success"] = True
            result["details"] = {
                "handoff_id": handoff.id,
                "to_agent": target_role,
            }
        else:
            result["details"] = {"error": "Failed to create handoff"}

    elif plan.action_type in ("none", "recommend"):
        result["success"] = True
        result["details"] = {"recommendation": plan.recommendation}

    return result
