"""Task lifecycle domain logic: transitions, blockers, and cycle detection.

Ensures task state machine integrity across API, Planner, and Repository.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set
from src.schemas import TaskStatus

VALID_PRIORITIES = {"low", "medium", "high", "critical"}

# Valid state transitions: {from_status: {allowed_to_statuses}}
PERMITTED_TRANSITIONS: Dict[str, Set[str]] = {
    TaskStatus.PENDING.value: {
        TaskStatus.IN_PROGRESS.value,
        TaskStatus.BLOCKED.value,
        TaskStatus.COMPLETED.value,
    },
    TaskStatus.IN_PROGRESS.value: {
        TaskStatus.PENDING.value,
        TaskStatus.BLOCKED.value,
        TaskStatus.COMPLETED.value,
    },
    TaskStatus.BLOCKED.value: {
        TaskStatus.PENDING.value,
        TaskStatus.IN_PROGRESS.value,
    },
    TaskStatus.COMPLETED.value: {
        TaskStatus.IN_PROGRESS.value,  # Reopened
        TaskStatus.PENDING.value,      # Reset
    },
}


class TaskLifecycleError(ValueError):
    """Raised when a task lifecycle rule is violated."""
    pass


class TaskDependencyCycleError(TaskLifecycleError):
    """Raised when adding a dependency would create a cycle."""
    pass


def validate_priority(priority: str) -> str:
    """Validate that task priority is recognized."""
    p = priority.lower().strip()
    if p not in VALID_PRIORITIES:
        raise TaskLifecycleError(
            f"Invalid priority '{priority}'. Allowed: {sorted(list(VALID_PRIORITIES))}"
        )
    return p


def validate_status_transition(
    current_status: str,
    new_status: str,
    active_blockers: Optional[List[dict]] = None,
) -> None:
    """Validate that transitioning from current_status to new_status is permitted.

    Raises TaskLifecycleError if transition is invalid.
    """
    valid_statuses = {s.value for s in TaskStatus}
    if new_status not in valid_statuses:
        raise TaskLifecycleError(
            f"Invalid target status '{new_status}'. Allowed: {sorted(list(valid_statuses))}"
        )

    # Transitioning to the exact same status is an idempotent no-op
    if current_status == new_status:
        return

    allowed = PERMITTED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise TaskLifecycleError(
            f"Invalid task status transition from '{current_status}' to '{new_status}'. "
            f"Allowed transitions from '{current_status}': {sorted(list(allowed)) or 'none'}"
        )

    # Rule: Cannot transition to 'completed' if any blocker task is not 'completed'
    if new_status == TaskStatus.COMPLETED.value and active_blockers:
        unresolved = [
            b.get("title", b.get("id", "Unknown"))
            for b in active_blockers
            if b.get("status") != TaskStatus.COMPLETED.value
        ]
        if unresolved:
            raise TaskLifecycleError(
                f"Cannot complete task: blocked by unresolved tasks: {', '.join(unresolved)}"
            )


def detect_dependency_cycle(
    blocked_id: str,
    blocker_id: str,
    existing_dependencies: List[tuple[str, str]],
) -> None:
    """Check if adding edge (blocked_id -[:BLOCKED_BY]-> blocker_id) creates a cycle.

    Args:
        blocked_id: ID of the task being blocked
        blocker_id: ID of the task that blocks it
        existing_dependencies: list of (blocked_task_id, blocker_task_id) tuples

    Raises:
        TaskDependencyCycleError if adding the dependency would cause a cycle.
    """
    if blocked_id == blocker_id:
        raise TaskDependencyCycleError(f"Task '{blocked_id}' cannot block itself")

    # Build adjacency map: task -> set of tasks that block it
    # If blocked_id blocks blocker_id directly or indirectly, adding blocked_id -> blocker_id is a cycle.
    adj: Dict[str, Set[str]] = {}
    for b_id, blk_id in existing_dependencies:
        adj.setdefault(b_id, set()).add(blk_id)

    # Check if blocker_id can reach blocked_id through existing dependencies
    visited: Set[str] = set()
    queue = [blocker_id]

    while queue:
        curr = queue.pop(0)
        if curr == blocked_id:
            raise TaskDependencyCycleError(
                f"Dependency cycle detected: adding blocker '{blocker_id}' to task '{blocked_id}' "
                f"creates a circular dependency loop."
            )
        if curr not in visited:
            visited.add(curr)
            for next_node in adj.get(curr, set()):
                if next_node not in visited:
                    queue.append(next_node)
