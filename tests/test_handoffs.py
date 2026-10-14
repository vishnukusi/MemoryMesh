"""Tests for handoffs — persistent inter-agent coordination."""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.schemas import (
    HandoffNode, AgentRunNode, TaskNode, ProjectNode,
    HandoffStatus, new_id,
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


def test_handoff_creation(repo):
    """A handoff should be created and retrievable from FalkorDB."""
    handoff = HandoffNode(
        from_agent="planner",
        to_agent="curator",
        task_id="test-task-1",
        context_summary="Please process this task",
    )
    result = repo.create_handoff(handoff)
    assert result.get("id") == handoff.id
    assert result.get("status") == "pending"

    # Retrieve
    retrieved = repo.get_handoff(handoff.id)
    assert retrieved is not None
    assert retrieved.get("from_agent") == "planner"


def test_handoff_claim(repo):
    """Claiming a handoff should change its status from pending to claimed."""
    handoff = HandoffNode(
        from_agent="planner", to_agent="investigator",
        context_summary="Investigate this",
    )
    repo.create_handoff(handoff)

    # Claim
    claimed = repo.claim_handoff(handoff.id)
    assert claimed is not None
    assert claimed.get("status") == "claimed"

    # Second claim should fail
    second = repo.claim_handoff(handoff.id)
    assert second is None


def test_handoff_completion(repo):
    """A claimed handoff can be completed."""
    handoff = HandoffNode(
        from_agent="planner", to_agent="verifier",
        context_summary="Verify this",
    )
    repo.create_handoff(handoff)
    repo.claim_handoff(handoff.id)

    completed = repo.complete_handoff(handoff.id)
    assert completed is not None
    assert completed.get("status") == "completed"


def test_handoff_with_context(repo):
    """A handoff should include its linked task context."""
    pid = f"test-proj-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Handoff Context Test")
    repo.create_project(project)

    task = TaskNode(title="API Work", project_id=pid)
    repo.create_task(task, pid)

    handoff = HandoffNode(
        from_agent="planner", to_agent="curator",
        task_id=task.id,
        context_summary="Work on the API task",
    )
    repo.create_handoff(handoff)

    # Retrieve with context
    ctx = repo.get_handoff_with_context(handoff.id)
    assert ctx.get("task") is not None
    assert ctx["task"].get("title") == "API Work"


def test_run_links_to_handoff(repo):
    """An agent run should link to its created handoff."""
    run = AgentRunNode(
        agent_name="planner",
        goal="Create a handoff",
        status="completed",
    )
    repo.create_agent_run(run)

    handoff = HandoffNode(
        from_agent="planner", to_agent="curator",
        context_summary="Context here",
    )
    repo.create_handoff(handoff)
    repo.link_run_to_handoff(run.id, handoff.id)

    # Verify run exists
    retrieved_run = repo.get_agent_run(run.id)
    assert retrieved_run is not None
