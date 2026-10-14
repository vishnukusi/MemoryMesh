"""Agent Orchestrator — coordinates the four specialist agents.

Controls the workflow: Curator → Investigator → Planner → Verifier.
Uses bounded execution, validated inputs, and clear success/failure states.
"""

from __future__ import annotations
import logging
import time
from datetime import datetime
from typing import Optional

from src.db.repository import GraphRepository
from src.schemas import (
    ChatRequest, ChatResponse, EpisodeNode, AgentRunNode,
    EvidenceRef, AgentTraceSummary, new_id,
)
from src.agents.curator import extract_from_message, process_extraction
from src.agents.investigator import investigate
from src.agents.planner import plan_action, execute_plan
from src.agents.verifier import verify_and_respond
from src.services.model_service import sync_check_ollama
from src.services.idempotency import (
    check_or_reserve_idempotency,
    finalize_idempotency_success,
    finalize_idempotency_failure,
    IdempotencyConflictError,
    IdempotencyConcurrentError,
)

logger = logging.getLogger(__name__)

# Maximum agent iterations to prevent infinite loops
MAX_AGENT_ITERATIONS = 4


async def process_chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message through the full agent pipeline.
    
    Workflow:
    1. Check or reserve idempotency
    2. Persist incoming message as an Episode
    3. Memory Curator extracts structured data
    4. Investigator retrieves relevant context
    5. Planner recommends action
    6. Verifier validates and produces final answer
    7. Finalize idempotency and return response
    """
    request_id = request.idempotency_key or new_id()
    traces: list[AgentTraceSummary] = []
    repo = GraphRepository(request.tenant_id)

    # Step 0: Check idempotency
    if request.idempotency_key:
        try:
            status, cached_resp = check_or_reserve_idempotency(repo, request)
            if status == "completed" and cached_resp:
                logger.info(f"Idempotent replay for key {request.idempotency_key}")
                return cached_resp
        except IdempotencyConflictError as ce:
            return ChatResponse(
                answer=f"Conflict: {ce}",
                session_id=request.session_id,
                request_id=request.idempotency_key,
                status="error",
                error="Idempotency key payload conflict",
            )
        except IdempotencyConcurrentError as cce:
            return ChatResponse(
                answer=f"Conflict: {cce}",
                session_id=request.session_id,
                request_id=request.idempotency_key,
                status="error",
                error="Concurrent operation in progress",
            )

    # Check Ollama availability
    ollama_ok = sync_check_ollama()

    try:
        # Step 1: Persist the incoming message as an Episode
        episode = EpisodeNode(
            id=request_id,  # Use idempotency key as episode ID
            session_id=request.session_id,
            project_id=request.project_id,
            content=request.message,
            actor="user",
            event_type="message",
        )
        repo.create_episode(episode)
        logger.info(f"Episode created: {episode.id}")

        # If Ollama is not available, return graceful degradation
        if not ollama_ok:
            fallback_resp = ChatResponse(
                answer="⚠️ Ollama is not available. Your message has been saved to memory. "
                       "To enable AI analysis, start Ollama with: `ollama serve` then `ollama pull qwen3:4b`\n\n"
                       "Your message was recorded and will be analyzed when the model is available.",
                session_id=request.session_id,
                request_id=request_id,
                status="partial",
                error="Ollama not available for AI inference",
            )
            if request.idempotency_key:
                finalize_idempotency_success(repo, request.idempotency_key, fallback_resp.model_dump())
            return fallback_resp

        # Step 2: Memory Curator — extract structured information
        curator_start = time.time()
        curator_run = AgentRunNode(
            agent_name="curator",
            goal=f"Extract information from: {request.message[:100]}",
        )
        repo.create_agent_run(curator_run)
        try:
            # Get existing tasks for context
            existing_tasks = repo.get_tasks_by_project(request.project_id)
            project = repo.get_project(request.project_id)
            project_context = f"Project: {project.get('name', 'Unknown')}" if project else ""

            extraction = await extract_from_message(
                request.message,
                project_context=project_context,
                existing_tasks=existing_tasks,
            )
            created = await process_extraction(repo, extraction, request.project_id, episode.id)

            curator_duration = int((time.time() - curator_start) * 1000)
            repo.complete_agent_run(
                curator_run.id, "completed",
                summary=f"Extracted {len(created.get('facts', []))} facts, "
                        f"{len(created.get('decisions', []))} decisions, "
                        f"{len(created.get('tasks', []))} tasks",
            )
            traces.append(AgentTraceSummary(
                agent_name="Memory Curator",
                goal="Extract and persist structured information",
                status="completed",
                records_written=[
                    f"{item.get('id', '?')}" for items in created.values() for item in items
                ],
                duration_ms=curator_duration,
            ))
        except Exception as exc:
            repo.complete_agent_run(curator_run.id, "failed", summary=f"Curator failed: {exc}")
            traces.append(AgentTraceSummary(
                agent_name="Memory Curator",
                goal="Extract and persist structured information",
                status="failed",
                records_written=[],
                duration_ms=int((time.time() - curator_start) * 1000),
            ))
            raise

        # Step 3: Investigator — retrieve relevant context
        inv_start = time.time()
        inv_run = AgentRunNode(
            agent_name="investigator",
            goal=f"Investigate: {request.message[:100]}",
        )
        repo.create_agent_run(inv_run)
        try:
            investigation = await investigate(repo, request.message, request.project_id)

            inv_duration = int((time.time() - inv_start) * 1000)
            records_read = (
                [f.get("id", "?") for f in investigation.relevant_facts] +
                [d.get("id", "?") for d in investigation.relevant_decisions] +
                [t.get("id", "?") for t in investigation.relevant_tasks]
            )
            repo.complete_agent_run(
                inv_run.id, "completed",
                summary=investigation.summary[:200],
            )
            traces.append(AgentTraceSummary(
                agent_name="Investigator",
                goal="Retrieve relevant context from graph",
                status="completed",
                records_read=records_read[:20],
                duration_ms=inv_duration,
            ))
        except Exception as exc:
            repo.complete_agent_run(inv_run.id, "failed", summary=f"Investigator failed: {exc}")
            traces.append(AgentTraceSummary(
                agent_name="Investigator",
                goal="Retrieve relevant context from graph",
                status="failed",
                records_read=[],
                duration_ms=int((time.time() - inv_start) * 1000),
            ))
            raise

        # Step 4: Planner — decide next action
        plan_start = time.time()
        plan_run = AgentRunNode(
            agent_name="planner",
            goal=f"Plan action for: {request.message[:100]}",
        )
        repo.create_agent_run(plan_run)
        try:
            plan = await plan_action(repo, request.message, investigation, request.project_id)
            plan_result = await execute_plan(repo, plan, request.project_id, plan_run.id)

            plan_duration = int((time.time() - plan_start) * 1000)
            repo.complete_agent_run(
                plan_run.id, "completed",
                summary=f"Action: {plan.action_type} — {plan.recommendation[:100]}",
            )
            
            handoff_id = plan_result.get("details", {}).get("handoff_id")
            traces.append(AgentTraceSummary(
                agent_name="Planner",
                goal="Decide and execute next action",
                status="completed",
                records_written=[handoff_id] if handoff_id else [],
                duration_ms=plan_duration,
            ))
        except Exception as exc:
            repo.complete_agent_run(plan_run.id, "failed", summary=f"Planner failed: {exc}")
            traces.append(AgentTraceSummary(
                agent_name="Planner",
                goal="Decide and execute next action",
                status="failed",
                records_written=[],
                duration_ms=int((time.time() - plan_start) * 1000),
            ))
            raise

        # Step 5: Verifier — validate and produce final answer
        ver_start = time.time()
        ver_run = AgentRunNode(
            agent_name="verifier",
            goal="Verify and produce final response",
        )
        repo.create_agent_run(ver_run)
        try:
            verification = await verify_and_respond(
                repo, request.message, investigation, plan, plan_result, request.project_id,
            )

            ver_duration = int((time.time() - ver_start) * 1000)
            repo.complete_agent_run(
                ver_run.id, "completed",
                summary=f"Verified: {verification.is_valid}, refs: {len(verification.evidence_refs)}",
            )
            traces.append(AgentTraceSummary(
                agent_name="Verifier",
                goal="Validate answer against evidence",
                status="completed",
                records_read=[r.node_id for r in verification.evidence_refs],
                duration_ms=ver_duration,
            ))
        except Exception as exc:
            repo.complete_agent_run(ver_run.id, "failed", summary=f"Verifier failed: {exc}")
            traces.append(AgentTraceSummary(
                agent_name="Verifier",
                goal="Validate answer against evidence",
                status="failed",
                records_read=[],
                duration_ms=int((time.time() - ver_start) * 1000),
            ))
            raise

        # Record the agent's response as an episode too
        response_episode = EpisodeNode(
            session_id=request.session_id,
            project_id=request.project_id,
            content=verification.final_answer[:2000],
            actor="assistant",
            event_type="response",
            source_event_id=episode.id,
        )
        repo.create_episode(response_episode)

        chat_resp = ChatResponse(
            answer=verification.final_answer,
            session_id=request.session_id,
            request_id=request_id,
            evidence=verification.evidence_refs,
            agent_traces=traces,
            handoff_created=handoff_id,
            status="success",
        )
        if request.idempotency_key:
            finalize_idempotency_success(
                repo, request.idempotency_key, chat_resp,
                reservation_token=request.reservation_token,
            )
        return chat_resp

    except Exception as e:
        logger.error(f"Orchestration error: {e}", exc_info=True)
        if request.idempotency_key:
            finalize_idempotency_failure(
                repo, request.idempotency_key, str(e),
                reservation_token=request.reservation_token,
            )
        return ChatResponse(
            answer=f"An error occurred while processing your request. Your message was saved. Error: {str(e)}",
            session_id=request.session_id,
            request_id=request_id,
            agent_traces=traces,
            status="error",
            error=str(e),
        )
