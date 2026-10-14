"""Tests for persistence — messages survive across sessions."""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.schemas import EpisodeNode, ProjectNode, new_id

# Skip all tests if FalkorDB is not available
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


def test_episode_persists(repo):
    """A message stored as an episode should be retrievable."""
    project = ProjectNode(id=f"test-proj-{new_id()[:8]}", name="Test Project")
    repo.create_project(project)

    ep = EpisodeNode(
        session_id="test-session-1",
        project_id=project.id,
        content="This message must persist",
        actor="user",
    )
    repo.create_episode(ep)

    # Retrieve
    episodes = repo.get_episodes_by_session("test-session-1")
    assert any(e.get("content") == "This message must persist" for e in episodes)


def test_cross_session_retrieval(repo):
    """A new session should retrieve memory from an earlier session."""
    project = ProjectNode(id=f"test-proj-{new_id()[:8]}", name="Cross Session Test")
    repo.create_project(project)

    # Session 1
    ep1 = EpisodeNode(
        session_id="session-old",
        project_id=project.id,
        content="Important fact from earlier session",
        actor="user",
    )
    repo.create_episode(ep1)

    # Session 2 retrieves project episodes (not session-bound)
    episodes = repo.get_episodes_by_project(project.id, limit=50)
    assert any("Important fact from earlier" in e.get("content", "") for e in episodes)


def test_idempotent_episode(repo):
    """Duplicate episode IDs should not create duplicate records."""
    project = ProjectNode(id=f"test-proj-{new_id()[:8]}", name="Idempotent Test")
    repo.create_project(project)

    ep_id = f"idem-{new_id()[:8]}"
    for _ in range(3):
        ep = EpisodeNode(
            id=ep_id,
            session_id="test-session-idem",
            project_id=project.id,
            content="Should only appear once",
            actor="user",
        )
        repo.create_episode(ep)

    episodes = repo.get_episodes_by_session("test-session-idem")
    matching = [e for e in episodes if e.get("id") == ep_id]
    assert len(matching) == 1


def test_project_create_and_retrieve_regression(repo):
    """Regression test: verify project can be created and retrieved through the repository layer.
    
    Verifies that create_project correctly passes all parameters (including updated_at),
    stores all fields in FalkorDB, and retrieves them accurately.
    """
    proj_id = f"reg-proj-{new_id()[:8]}"
    project = ProjectNode(
        id=proj_id,
        name="Regression Verification Project",
        description="Verifies create_project succeeds with all query parameters",
    )
    # Create project through repository layer
    created = repo.create_project(project)
    assert created.get("id") == proj_id
    assert created.get("name") == "Regression Verification Project"
    assert created.get("description") == "Verifies create_project succeeds with all query parameters"
    assert created.get("status") == "active"
    assert "created_at" in created and created["created_at"].endswith("Z")
    assert "updated_at" in created and created["updated_at"].endswith("Z")

    # Retrieve project through repository layer
    retrieved = repo.get_project(proj_id)
    assert retrieved is not None
    assert retrieved.get("id") == proj_id
    assert retrieved.get("name") == "Regression Verification Project"
    assert retrieved.get("description") == "Verifies create_project succeeds with all query parameters"
    assert retrieved.get("status") == "active"
    assert retrieved.get("created_at") == project.created_at
    assert retrieved.get("updated_at") == project.updated_at

    # Verify idempotency / update on re-creation without duplicate records
    updated_project = ProjectNode(
        id=proj_id,
        name="Regression Verification Project Updated",
        description="Updated description",
    )
    repo.create_project(updated_project)

    retrieved_again = repo.get_project(proj_id)
    assert retrieved_again is not None
    assert retrieved_again.get("id") == proj_id
    assert retrieved_again.get("name") == "Regression Verification Project Updated"
    assert retrieved_again.get("description") == "Updated description"

    # Ensure no duplicates in get_all_projects
    all_projects = repo.get_all_projects()
    matches = [p for p in all_projects if p.get("id") == proj_id]
    assert len(matches) == 1
