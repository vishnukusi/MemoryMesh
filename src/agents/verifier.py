"""Verifier / Response Agent — validates answers against stored evidence.

Checks that cited records exist, facts are current, and produces
the final user-facing response with evidence references.
"""

from __future__ import annotations
import logging
from typing import Optional

from src.db.repository import GraphRepository
from src.schemas import (
    VerificationResult, EvidenceRef, InvestigationResult, PlannerAction,
)
from src.services.model_service import generate_json

logger = logging.getLogger(__name__)

VERIFIER_SYSTEM_PROMPT = """You are the Verifier agent for MemoryMesh.

Your job: Given the investigation findings and planned action, produce a FINAL
verified answer for the user.

RULES:
- Verify that any cited record IDs appear in the provided data.
- Check whether facts are current (status='current') vs superseded.
- If evidence is missing, say so clearly.
- Produce a clear, helpful answer the user can understand.
- Include evidence references (node IDs) so the user can inspect them.
- Do NOT fabricate record IDs or data.
- State limitations honestly.
- If a task status changed, confirm the actual new state.

Return JSON:
{
  "is_valid": true,
  "final_answer": "Your verified answer to the user",
  "evidence_refs": [{"node_type": "Fact|Decision|Task|Episode", "node_id": "...", "summary": "..."}],
  "warnings": ["any concerns about data quality or completeness"],
  "missing_evidence": ["any expected evidence that was not found"]
}

Return raw JSON only."""


async def verify_and_respond(
    repo: GraphRepository,
    user_question: str,
    investigation: InvestigationResult,
    plan: PlannerAction,
    plan_result: dict,
    project_id: str,
) -> VerificationResult:
    """Verify findings and produce final response."""

    # Build context for verification
    context = f"User question: {user_question}\n\n"
    context += f"Investigation summary: {investigation.summary}\n\n"
    context += f"Planner action: {plan.action_type} - {plan.recommendation}\n"
    context += f"Planner reasoning: {plan.reasoning}\n\n"

    if plan_result:
        context += f"Action result: {plan_result}\n\n"

    # Include raw evidence
    if investigation.relevant_facts:
        context += "Facts found:\n" + "\n".join(
            f"- [{f.get('id', '?')}] {f.get('subject', '?')}: {f.get('value', '?')} (status: {f.get('status', '?')})"
            for f in investigation.relevant_facts
        ) + "\n\n"

    if investigation.relevant_decisions:
        context += "Decisions found:\n" + "\n".join(
            f"- [{d.get('id', '?')}] {d.get('title', '?')}: {d.get('chosen_option', '?')} — {d.get('rationale', '')}"
            for d in investigation.relevant_decisions
        ) + "\n\n"

    if investigation.relevant_tasks:
        context += "Tasks found:\n" + "\n".join(
            f"- [{t.get('id', '?')}] {t.get('title', '?')} (status: {t.get('status', '?')})"
            for t in investigation.relevant_tasks
        ) + "\n\n"

    if investigation.relevant_episodes:
        context += "Supporting episodes:\n" + "\n".join(
            f"- [{e.get('id', '?')}] {e.get('content', '?')[:150]}"
            for e in investigation.relevant_episodes
        ) + "\n\n"

    user_prompt = f"""Verify and produce a final answer:

{context}

Produce a clear, verified answer with evidence references."""

    try:
        raw_result = await generate_json(VERIFIER_SYSTEM_PROMPT, user_prompt)
        if raw_result:
            result = VerificationResult.model_validate(raw_result)
            # Deterministic evidence verification
            valid_evidence: list[EvidenceRef] = []
            warnings = list(result.warnings or [])
            missing = list(result.missing_evidence or [])

            for ref in result.evidence_refs:
                exists = False
                if ref.node_type == "Fact":
                    f = repo.get_fact(ref.node_id)
                    if f and (not f.get("project_id") or f.get("project_id") == project_id):
                        exists = True
                        if f.get("status") == "superseded":
                            warnings.append(f"Fact {ref.node_id} cited is superseded.")
                elif ref.node_type == "Decision":
                    d = repo.get_decision(ref.node_id)
                    if d and (not d.get("project_id") or d.get("project_id") == project_id):
                        exists = True
                elif ref.node_type == "Task":
                    t = repo.get_task(ref.node_id)
                    if t and (not t.get("project_id") or t.get("project_id") == project_id):
                        exists = True
                elif ref.node_type == "Episode":
                    e = repo.get_episode(ref.node_id)
                    if e and (not e.get("project_id") or e.get("project_id") == project_id):
                        exists = True

                if exists:
                    valid_evidence.append(ref)
                else:
                    warnings.append(f"Cited evidence {ref.node_id} ({ref.node_type}) could not be verified in project {project_id}.")

            if plan_result and not plan_result.get("success", False):
                err = plan_result.get("details", {}).get("error", "action failed")
                warnings.append(f"Planned action '{plan.action_type}' failed: {err}")

            result.evidence_refs = valid_evidence
            result.warnings = warnings
            result.missing_evidence = missing
            return result
    except Exception as e:
        logger.error(f"Verifier failed: {e}")

    # Fallback: construct answer from available data
    evidence_refs = []
    answer_parts = []
    fallback_warnings = ["Response generated without full LLM verification — using raw graph data."]

    if investigation.summary:
        answer_parts.append(investigation.summary)
    if plan.recommendation:
        answer_parts.append(f"\n**Recommendation:** {plan.recommendation}")

    if plan_result and not plan_result.get("success", False):
        err = plan_result.get("details", {}).get("error", "action failed")
        fallback_warnings.append(f"Planned action '{plan.action_type}' failed: {err}")

    # Add evidence from investigation
    for f in (investigation.relevant_facts or [])[:3]:
        evidence_refs.append(EvidenceRef(
            node_type="Fact",
            node_id=f.get("id", "unknown"),
            summary=f"{f.get('subject', '?')}: {f.get('value', '?')}",
        ))
    for d in (investigation.relevant_decisions or [])[:3]:
        evidence_refs.append(EvidenceRef(
            node_type="Decision",
            node_id=d.get("id", "unknown"),
            summary=f"{d.get('title', '?')}: {d.get('chosen_option', '?')}",
        ))
    for t in (investigation.relevant_tasks or [])[:3]:
        evidence_refs.append(EvidenceRef(
            node_type="Task",
            node_id=t.get("id", "unknown"),
            summary=f"{t.get('title', '?')} ({t.get('status', '?')})",
        ))

    return VerificationResult(
        is_valid=True,
        final_answer="\n".join(answer_parts) if answer_parts else "I retrieved relevant records but could not generate a synthesis. Please check the evidence references.",
        evidence_refs=evidence_refs,
        warnings=fallback_warnings,
    )
