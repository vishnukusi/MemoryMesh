"""Memory update — handles modifying existing memories safely."""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from src.db.repository import GraphRepository
from src.schemas import FactNode, EpisodeNode, FactStatus, new_id


def update_fact(
    repo: GraphRepository,
    old_fact_id: str,
    new_value: str,
    project_id: str,
    episode_id: Optional[str] = None,
    confidence: float = 0.8,
) -> dict:
    """Supersede an existing fact with a new value.
    
    The old fact is marked superseded with a valid_to timestamp.
    A new fact is created with a SUPERSEDES relationship.
    """
    old_fact = repo.get_fact(old_fact_id)
    if not old_fact:
        return {"error": f"Fact {old_fact_id} not found"}

    new_fact = FactNode(
        subject=old_fact.get("subject", ""),
        predicate=old_fact.get("predicate", ""),
        value=new_value,
        confidence=confidence,
        status=FactStatus.CURRENT.value,
        version=old_fact.get("version", 1) + 1,
    )
    return repo.supersede_fact(old_fact_id, new_fact, project_id, episode_id)


def update_task_status(
    repo: GraphRepository,
    task_id: str,
    new_status: str,
    project_id: str,
    expected_revision: Optional[int] = None,
) -> dict:
    """Update task status with optimistic concurrency and history tracking."""
    task = repo.get_task(task_id)
    if not task:
        return {"error": f"Task {task_id} not found"}

    # Ensure task belongs to the active project
    task_project = task.get("project_id", "")
    if project_id and task_project and task_project != project_id:
        return {"error": f"Task '{task_id}' does not belong to project '{project_id}'"}

    target_revision = expected_revision if expected_revision is not None else task.get("revision", 1)

    try:
        result = repo.update_task_status(
            task_id,
            new_status,
            expected_revision=target_revision,
            enforce_lifecycle=True,
        )
    except Exception as e:
        return {"error": str(e)}

    if result is None:
        return {
            "error": f"Concurrent modification detected: task '{task_id}' revision mismatch (expected {target_revision}).",
            "conflict": True,
        }

    # Record the status change as an episode
    change_episode = EpisodeNode(
        session_id="system",
        project_id=project_id or task_project,
        content=f"Task '{task.get('title')}' status changed from {task.get('status')} to {new_status}",
        actor="system",
        event_type="task_update",
    )
    repo.create_episode(change_episode)

    return result
