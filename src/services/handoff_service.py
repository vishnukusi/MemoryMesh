"""Handoff service — manages inter-agent work handoffs.

Handoffs persist in FalkorDB and survive restarts.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional

from src.db.repository import GraphRepository
from src.schemas import HandoffNode, HandoffStatus, new_id

logger = logging.getLogger(__name__)


async def create_handoff(
    repo: GraphRepository,
    from_agent: str,
    to_agent: str,
    task_id: str,
    context_summary: str,
    run_id: Optional[str] = None,
) -> dict:
    """Create a new handoff between agents."""
    handoff = HandoffNode(
        from_agent=from_agent,
        to_agent=to_agent,
        task_id=task_id,
        context_summary=context_summary,
    )
    result = repo.create_handoff(handoff)
    if run_id:
        repo.link_run_to_handoff(run_id, handoff.id)
    logger.info(f"Handoff created: {handoff.id} from {from_agent} to {to_agent}")
    return result


async def claim_handoff(repo: GraphRepository, handoff_id: str) -> Optional[dict]:
    """Claim a pending handoff. Returns None if already claimed/completed."""
    result = repo.claim_handoff(handoff_id)
    if result is None:
        logger.warning(f"Handoff {handoff_id} could not be claimed (not pending)")
    return result


async def complete_handoff(repo: GraphRepository, handoff_id: str) -> Optional[dict]:
    """Mark a claimed handoff as completed."""
    return repo.complete_handoff(handoff_id)


async def fail_handoff(repo: GraphRepository, handoff_id: str) -> Optional[dict]:
    """Mark a handoff as failed."""
    return repo.fail_handoff(handoff_id)


async def get_handoff_context(repo: GraphRepository, handoff_id: str) -> dict:
    """Retrieve a handoff with its full context for the receiving agent."""
    return repo.get_handoff_with_context(handoff_id)
