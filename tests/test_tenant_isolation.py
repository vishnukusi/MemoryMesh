"""Tests for tenant isolation — two tenants must not see each other's data."""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import check_connection
from src.db.repository import GraphRepository
from src.db.schema import bootstrap_schema
from src.schemas import (
    ProjectNode, FactNode, EpisodeNode, DecisionNode, new_id,
)
from src.config import settings

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="FalkorDB not available"
)

TENANT_A = "tenant_alpha"
TENANT_B = "tenant_beta"


@pytest.fixture(autouse=True)
def setup_schemas():
    bootstrap_schema(TENANT_A)
    bootstrap_schema(TENANT_B)


@pytest.fixture
def repo_a():
    return GraphRepository(TENANT_A)


@pytest.fixture
def repo_b():
    return GraphRepository(TENANT_B)


def test_separate_graphs():
    """Each tenant should use a different graph name."""
    name_a = settings.get_graph_name(TENANT_A)
    name_b = settings.get_graph_name(TENANT_B)
    assert name_a != name_b
    assert TENANT_A.replace("tenant_", "") in name_a.replace("memorymesh_", "")
    assert TENANT_B.replace("tenant_", "") in name_b.replace("memorymesh_", "")


def test_invalid_tenant_rejected():
    """An invalid tenant ID should be rejected."""
    with pytest.raises(ValueError):
        settings.get_graph_name("evil_tenant")


def test_secret_fact_isolation(repo_a, repo_b):
    """A secret fact in Tenant A must not appear in Tenant B."""
    # Create secret fact in Alpha
    pid_a = f"test-proj-{new_id()[:8]}"
    project_a = ProjectNode(id=pid_a, name="Alpha Secret Project")
    repo_a.create_project(project_a)

    secret_fact = FactNode(
        subject="secret_code",
        predicate="is",
        value="ALPHA_SECRET_XYZ123",
        confidence=1.0,
    )
    repo_a.create_fact(secret_fact, pid_a)

    # Verify Alpha can see it
    alpha_facts = repo_a.search_facts("secret_code", limit=10)
    assert any(f.get("value") == "ALPHA_SECRET_XYZ123" for f in alpha_facts)

    # Verify Beta CANNOT see it
    beta_facts = repo_b.search_facts("secret_code", limit=10)
    assert not any(f.get("value") == "ALPHA_SECRET_XYZ123" for f in beta_facts)


def test_episode_isolation(repo_a, repo_b):
    """Episodes in one tenant must not leak to another."""
    pid_a = f"test-proj-{new_id()[:8]}"
    project_a = ProjectNode(id=pid_a, name="Alpha Episode Project")
    repo_a.create_project(project_a)

    ep = EpisodeNode(
        session_id="alpha-secret-session",
        project_id=pid_a,
        content="This is confidential Alpha information about passwords",
        actor="user",
    )
    repo_a.create_episode(ep)

    # Alpha sees it
    alpha_eps = repo_a.search_episodes(pid_a, "confidential", limit=10)
    assert len(alpha_eps) >= 1

    # Beta doesn't
    beta_eps = repo_b.search_episodes(pid_a, "confidential", limit=10)
    assert len(beta_eps) == 0


def test_decision_isolation(repo_a, repo_b):
    """Decisions in one tenant must not appear in another."""
    pid_a = f"test-proj-{new_id()[:8]}"
    project_a = ProjectNode(id=pid_a, name="Alpha Decision Project")
    repo_a.create_project(project_a)

    dec = DecisionNode(
        title="Secret Alpha Decision",
        chosen_option="Option X",
        rationale="Because Alpha said so",
    )
    repo_a.create_decision(dec, pid_a)

    # Alpha has it
    alpha_decs = repo_a.search_decisions("Secret Alpha", limit=10)
    assert any(d.get("title") == "Secret Alpha Decision" for d in alpha_decs)

    # Beta doesn't
    beta_decs = repo_b.search_decisions("Secret Alpha", limit=10)
    assert not any(d.get("title") == "Secret Alpha Decision" for d in beta_decs)


def test_project_isolation(repo_a, repo_b):
    """Projects in one tenant must not appear in another."""
    pid = f"test-isolation-{new_id()[:8]}"
    project = ProjectNode(id=pid, name="Alpha Only Project XYZ")
    repo_a.create_project(project)

    # Alpha sees it
    alpha_projects = repo_a.get_all_projects()
    assert any(p.get("name") == "Alpha Only Project XYZ" for p in alpha_projects)

    # Beta doesn't
    beta_projects = repo_b.get_all_projects()
    assert not any(p.get("name") == "Alpha Only Project XYZ" for p in beta_projects)
