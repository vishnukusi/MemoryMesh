"""Tests for memory retrieval — facts, decisions, episodes."""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.schemas import (
    ProjectNode, EpisodeNode, FactNode, DecisionNode, new_id,
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


def test_decision_with_evidence(repo):
    """A decision should be retrievable with its supporting episode."""
    pid = f"test-proj-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Decision Test")
    repo.create_project(project)

    ep = EpisodeNode(
        session_id="s1", project_id=pid,
        content="We chose React because the team knows it",
        actor="user",
    )
    repo.create_episode(ep)

    dec = DecisionNode(
        title="Frontend Framework",
        chosen_option="React",
        rationale="Team familiarity",
    )
    repo.create_decision(dec, pid, ep.id)

    result = repo.get_decision_with_evidence(dec.id)
    assert result.get("chosen_option") == "React"
    assert len(result.get("supporting_episodes", [])) >= 1


def test_fact_search(repo):
    """Facts should be searchable by subject."""
    pid = f"test-proj-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Fact Search Test")
    repo.create_project(project)

    fact = FactNode(
        subject="database",
        predicate="type",
        value="PostgreSQL",
        confidence=0.9,
    )
    repo.create_fact(fact, pid)

    results = repo.search_facts("database", limit=10)
    assert any(f.get("value") == "PostgreSQL" for f in results)


def test_episode_search(repo):
    """Episodes should be searchable by content."""
    pid = f"test-proj-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Episode Search Test")
    repo.create_project(project)

    ep = EpisodeNode(
        session_id="s1", project_id=pid,
        content="The deadline is next Friday for the product launch",
        actor="user",
    )
    repo.create_episode(ep)

    results = repo.search_episodes(pid, "deadline", limit=10)
    assert any("deadline" in e.get("content", "").lower() for e in results)
