"""Memory ingestion — handles storing new memories from user messages."""

from __future__ import annotations
from typing import Optional
from src.db.repository import GraphRepository
from src.schemas import EpisodeNode, new_id


def ingest_message(
    repo: GraphRepository,
    message: str,
    session_id: str,
    project_id: str,
    actor: str = "user",
    event_type: str = "message",
    idempotency_key: Optional[str] = None,
) -> dict:
    """Store a message as an Episode in the graph.

    Uses MERGE on ID for idempotency — duplicate IDs won't create duplicates.
    """
    episode = EpisodeNode(
        id=idempotency_key or new_id(),
        session_id=session_id,
        project_id=project_id,
        content=message,
        actor=actor,
        event_type=event_type,
    )
    return repo.create_episode(episode)
