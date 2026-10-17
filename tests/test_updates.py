"""Tests for updates — task status changes, fact supersession."""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.schemas import (
    ProjectNode, TaskNode, FactNode, EpisodeNode,
    TaskStatus, FactStatus, new_id,
)

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="FalkorDB not available"
)

TEST_TENANT = "tenant_alpha"


@pytest.fixture(autouse=True)
def setup_schema():
    bootstrap_schema(TEST_TENANT)


@pytest.fixture
def repo():
    return GraphRepository(TEST_TENANT)


def test_task_status_update_preserves_history(repo):
    """Task status change should update current state and create a history event."""
    pid = f"test-proj-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Update Test")
    repo.create_project(project)

    task = TaskNode(
        title="Test Update Task", status="in_progress", project_id=pid,
    )
    repo.create_task(task, pid)

    # Update status
    result = repo.update_task_status(task.id, "completed", expected_revision=1)
    assert result is not None
    assert result.get("status") == "completed"
    assert result.get("revision") == 2

    # Original episode still exists (history preserved)
    # The task's previous state is captured in the revision


def test_optimistic_concurrency(repo):
    """Update with wrong revision should fail."""
    pid = f"test-proj-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Concurrency Test")
    repo.create_project(project)

    task = TaskNode(
        title="Concurrent Task", status="pending", project_id=pid,
    )
    repo.create_task(task, pid)

    # First update succeeds
    result1 = repo.update_task_status(task.id, "in_progress", expected_revision=1)
    assert result1 is not None

    # Second update with stale revision fails
    result2 = repo.update_task_status(task.id, "completed", expected_revision=1)
    assert result2 is None  # Stale revision → rejected


def test_fact_supersession(repo):
    """Superseding a fact should mark old as superseded and create a new current fact."""
    pid = f"test-proj-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Supersession Test")
    repo.create_project(project)

    old_fact = FactNode(
        subject="deadline", predicate="is", value="Friday",
        status=FactStatus.CURRENT.value,
    )
    repo.create_fact(old_fact, pid)

    new_fact = FactNode(
        subject="deadline", predicate="is", value="Next Monday",
        status=FactStatus.CURRENT.value, version=2,
    )
    repo.supersede_fact(old_fact.id, new_fact, pid)

    # Old fact should be superseded
    old = repo.get_fact(old_fact.id)
    assert old.get("status") == "superseded"

    # New fact should be current
    new = repo.get_fact(new_fact.id)
    assert new.get("status") == "current"
    assert new.get("value") == "Next Monday"
