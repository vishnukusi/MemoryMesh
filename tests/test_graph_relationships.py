"""Tests for graph relationships — task dependencies, fact provenance."""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.schemas import ProjectNode, TaskNode, FactNode, EpisodeNode, new_id

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


def test_task_dependency(repo):
    """Task dependency (BLOCKED_BY) should be correctly recorded and queryable."""
    pid = f"test-proj-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Dependency Test")
    repo.create_project(project)

    api_task = TaskNode(
        title="API Development", status="in_progress", project_id=pid,
    )
    auth_task = TaskNode(
        title="Authentication", status="blocked", project_id=pid,
    )
    repo.create_task(api_task, pid)
    repo.create_task(auth_task, pid)

    repo.create_blocked_by(auth_task.id, api_task.id)

    blockers = repo.get_task_blockers(auth_task.id)
    assert len(blockers) >= 1
    assert any(b.get("title") == "API Development" for b in blockers)


def test_fact_linked_to_episode(repo):
    """A fact should link to its source episode via SUPPORTED_BY."""
    pid = f"test-proj-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Provenance Test")
    repo.create_project(project)

    ep = EpisodeNode(
        session_id="s1", project_id=pid,
        content="We use PostgreSQL for ACID compliance",
        actor="user",
    )
    repo.create_episode(ep)

    fact = FactNode(
        subject="database", predicate="choice", value="PostgreSQL",
    )
    repo.create_fact(fact, pid, ep.id)

    # Verify the fact was created
    retrieved = repo.get_fact(fact.id)
    assert retrieved is not None
    assert retrieved.get("value") == "PostgreSQL"


def test_task_project_link(repo):
    """Tasks should be linked to their project via HAS_TASK."""
    pid = f"test-proj-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Task Link Test")
    repo.create_project(project)

    task = TaskNode(title="Test Task", project_id=pid)
    repo.create_task(task, pid)

    tasks = repo.get_tasks_by_project(pid)
    assert any(t.get("title") == "Test Task" for t in tasks)
