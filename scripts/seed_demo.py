"""Seed demonstration data for MemoryMesh.

Creates consistent demo data for two tenants.
Safe to run multiple times — uses MERGE for idempotency.
"""

from __future__ import annotations
import json
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import get_graph, check_connection
from src.db.schema import bootstrap_schema
from src.db.repository import GraphRepository
from src.schemas import (
    ProjectNode, PersonNode, EpisodeNode, FactNode, DecisionNode,
    TaskNode, ProcedureNode, HandoffNode, AgentRunNode,
    TaskStatus, FactStatus, new_id,
)

logger = logging.getLogger(__name__)

# Fixed IDs for repeatable seeding (running twice won't duplicate)
ALPHA_IDS = {
    "project": "proj-alpha-001",
    "person_alice": "person-alice-001",
    "person_bob": "person-bob-001",
    "episode_1": "ep-alpha-001",
    "episode_2": "ep-alpha-002",
    "episode_3": "ep-alpha-003",
    "fact_launch": "fact-alpha-launch",
    "fact_db": "fact-alpha-db",
    "decision_pg": "dec-alpha-pg",
    "task_api": "task-alpha-api",
    "task_auth": "task-alpha-auth",
    "task_frontend": "task-alpha-frontend",
    "procedure_api": "proc-alpha-api",
    "handoff_1": "handoff-alpha-001",
    "run_1": "run-alpha-001",
}

BETA_IDS = {
    "project": "proj-beta-001",
    "person_carol": "person-carol-001",
    "episode_1": "ep-beta-001",
    "episode_2": "ep-beta-002",
    "fact_deadline": "fact-beta-deadline",
    "fact_framework": "fact-beta-framework",
    "decision_react": "dec-beta-react",
    "task_design": "task-beta-design",
    "task_backend": "task-beta-backend",
    "procedure_deploy": "proc-beta-deploy",
}


def seed_tenant_alpha(repo: GraphRepository) -> dict:
    """Seed Tenant Alpha with a software launch project."""
    summary = {"created": []}

    # Project
    project = ProjectNode(
        id=ALPHA_IDS["project"],
        name="Phoenix App Launch",
        description="Internal tool rewrite with a Friday launch deadline",
    )
    repo.create_project(project)
    summary["created"].append(f"Project: {project.name}")

    # People
    alice = PersonNode(id=ALPHA_IDS["person_alice"], name="Alice", role="Backend Lead")
    bob = PersonNode(id=ALPHA_IDS["person_bob"], name="Bob", role="Frontend Lead")
    repo.create_person(alice)
    repo.create_person(bob)
    summary["created"].extend(["Person: Alice", "Person: Bob"])

    # Episode 1: Initial planning conversation
    ep1 = EpisodeNode(
        id=ALPHA_IDS["episode_1"],
        session_id="seed-session-alpha-1",
        project_id=project.id,
        content="Our launch is Friday. We selected PostgreSQL because our data is relational and we need strong ACID guarantees. Authentication depends on the API, and the API is still in progress.",
        actor="user",
        event_type="message",
        timestamp="2026-10-12T10:00:00Z",
    )
    repo.create_episode(ep1)

    # Episode 2: Follow-up
    ep2 = EpisodeNode(
        id=ALPHA_IDS["episode_2"],
        session_id="seed-session-alpha-1",
        project_id=project.id,
        content="Alice is handling the API development. Bob is working on the frontend. The API needs to pass all integration tests before we can mark it complete.",
        actor="user",
        event_type="message",
        timestamp="2026-10-12T10:15:00Z",
    )
    repo.create_episode(ep2)

    # Episode 3: Status update
    ep3 = EpisodeNode(
        id=ALPHA_IDS["episode_3"],
        session_id="seed-session-alpha-2",
        project_id=project.id,
        content="The API endpoints are mostly done but the authentication middleware still needs the API to be finalized first.",
        actor="user",
        event_type="message",
        timestamp="2026-10-13T09:00:00Z",
    )
    repo.create_episode(ep3)
    summary["created"].append("3 Episodes")

    # Facts
    fact_launch = FactNode(
        id=ALPHA_IDS["fact_launch"],
        subject="Phoenix App Launch",
        predicate="deadline",
        value="Friday",
        confidence=0.95,
        status=FactStatus.CURRENT.value,
        valid_from="2026-10-12T10:00:00Z",
    )
    repo.create_fact(fact_launch, project.id, ep1.id)

    fact_db = FactNode(
        id=ALPHA_IDS["fact_db"],
        subject="Phoenix App",
        predicate="database_choice",
        value="PostgreSQL",
        confidence=0.95,
        status=FactStatus.CURRENT.value,
        valid_from="2026-10-12T10:00:00Z",
    )
    repo.create_fact(fact_db, project.id, ep1.id)
    summary["created"].append("2 Facts")

    # Decision
    decision = DecisionNode(
        id=ALPHA_IDS["decision_pg"],
        title="Database Selection",
        chosen_option="PostgreSQL",
        rationale="Our data is relational and we need strong ACID guarantees",
        status="active",
    )
    repo.create_decision(decision, project.id, ep1.id)
    summary["created"].append("1 Decision: Database Selection")

    # Tasks
    task_api = TaskNode(
        id=ALPHA_IDS["task_api"],
        title="API Development",
        description="Build and test all REST API endpoints",
        status=TaskStatus.IN_PROGRESS.value,
        priority="high",
        owner_id=alice.id,
        project_id=project.id,
    )
    repo.create_task(task_api, project.id)

    task_auth = TaskNode(
        id=ALPHA_IDS["task_auth"],
        title="Authentication Implementation",
        description="Implement authentication middleware",
        status=TaskStatus.BLOCKED.value,
        priority="high",
        project_id=project.id,
    )
    repo.create_task(task_auth, project.id)

    task_frontend = TaskNode(
        id=ALPHA_IDS["task_frontend"],
        title="Frontend Development",
        description="Build the user interface",
        status=TaskStatus.IN_PROGRESS.value,
        priority="medium",
        owner_id=bob.id,
        project_id=project.id,
    )
    repo.create_task(task_frontend, project.id)

    # Create dependency: Auth blocked by API
    repo.create_blocked_by(task_auth.id, task_api.id)
    summary["created"].append("3 Tasks (with dependency: Auth BLOCKED_BY API)")

    # Procedure
    procedure = ProcedureNode(
        id=ALPHA_IDS["procedure_api"],
        title="API Completion Checklist",
        description="Steps to verify API task is ready for completion",
        steps_json=json.dumps([
            "All endpoints implemented and documented",
            "Integration tests pass with 100% of critical paths covered",
            "API documentation reviewed by team lead",
            "Performance benchmarks meet SLA requirements",
            "Authentication middleware team notified of readiness",
        ]),
        version=1,
        approved=True,
    )
    repo.create_procedure(procedure, project.id)
    summary["created"].append("1 Procedure: API Completion Checklist (approved)")

    # Agent Run + Handoff (demo)
    run = AgentRunNode(
        id=ALPHA_IDS["run_1"],
        agent_name="planner",
        goal="Coordinate API task priority for launch deadline",
        status="completed",
        summary="Determined API task should be prioritized and handed off for focused work",
        started_at="2026-10-13T09:30:00Z",
        completed_at="2026-10-13T09:30:05Z",
    )
    repo.create_agent_run(run)

    handoff = HandoffNode(
        id=ALPHA_IDS["handoff_1"],
        from_agent="planner",
        to_agent="curator",
        task_id=task_api.id,
        context_summary="API Development is blocking Authentication. Launch is Friday. "
                        "Prioritize API completion. Alice is the owner. "
                        "Follow the API Completion Checklist procedure.",
        status="pending",
    )
    repo.create_handoff(handoff)
    repo.link_run_to_handoff(run.id, handoff.id)
    summary["created"].append("1 Agent Run + 1 Handoff")

    return summary


def seed_tenant_beta(repo: GraphRepository) -> dict:
    """Seed Tenant Beta with a different project."""
    summary = {"created": []}

    # Project
    project = ProjectNode(
        id=BETA_IDS["project"],
        name="DataViz Dashboard",
        description="Real-time analytics dashboard for marketing team",
    )
    repo.create_project(project)
    summary["created"].append(f"Project: {project.name}")

    # Person
    carol = PersonNode(id=BETA_IDS["person_carol"], name="Carol", role="Full Stack Developer")
    repo.create_person(carol)
    summary["created"].append("Person: Carol")

    # Episodes
    ep1 = EpisodeNode(
        id=BETA_IDS["episode_1"],
        session_id="seed-session-beta-1",
        project_id=project.id,
        content="We need the dashboard ready by end of month. We chose React for the frontend because the team already knows it. The backend API needs to support real-time WebSocket connections.",
        actor="user",
        event_type="message",
        timestamp="2026-10-11T14:00:00Z",
    )
    repo.create_episode(ep1)

    ep2 = EpisodeNode(
        id=BETA_IDS["episode_2"],
        session_id="seed-session-beta-1",
        project_id=project.id,
        content="Carol will handle both the design and the backend. The design mockups should be approved before backend work starts.",
        actor="user",
        event_type="message",
        timestamp="2026-10-11T14:20:00Z",
    )
    repo.create_episode(ep2)
    summary["created"].append("2 Episodes")

    # Facts
    fact_deadline = FactNode(
        id=BETA_IDS["fact_deadline"],
        subject="DataViz Dashboard",
        predicate="deadline",
        value="End of month",
        confidence=0.9,
        status=FactStatus.CURRENT.value,
    )
    repo.create_fact(fact_deadline, project.id, ep1.id)

    fact_framework = FactNode(
        id=BETA_IDS["fact_framework"],
        subject="DataViz Dashboard",
        predicate="frontend_framework",
        value="React",
        confidence=0.95,
        status=FactStatus.CURRENT.value,
    )
    repo.create_fact(fact_framework, project.id, ep1.id)
    summary["created"].append("2 Facts")

    # Decision
    decision = DecisionNode(
        id=BETA_IDS["decision_react"],
        title="Frontend Framework Selection",
        chosen_option="React",
        rationale="Team already has React expertise, reducing ramp-up time",
    )
    repo.create_decision(decision, project.id, ep1.id)
    summary["created"].append("1 Decision: Frontend Framework Selection")

    # Tasks
    task_design = TaskNode(
        id=BETA_IDS["task_design"],
        title="Design Mockups",
        description="Create and get approval for dashboard design mockups",
        status=TaskStatus.IN_PROGRESS.value,
        priority="high",
        owner_id=carol.id,
        project_id=project.id,
    )
    repo.create_task(task_design, project.id)

    task_backend = TaskNode(
        id=BETA_IDS["task_backend"],
        title="Backend WebSocket API",
        description="Build real-time WebSocket API for live data streaming",
        status=TaskStatus.BLOCKED.value,
        priority="high",
        owner_id=carol.id,
        project_id=project.id,
    )
    repo.create_task(task_backend, project.id)

    # Backend blocked by Design
    repo.create_blocked_by(task_backend.id, task_design.id)
    summary["created"].append("2 Tasks (Backend BLOCKED_BY Design)")

    # Procedure
    procedure = ProcedureNode(
        id=BETA_IDS["procedure_deploy"],
        title="Dashboard Deployment Checklist",
        description="Steps before deploying the dashboard to production",
        steps_json=json.dumps([
            "All components render correctly with test data",
            "WebSocket connections handle reconnection gracefully",
            "Performance tested with 1000 concurrent connections",
            "Accessibility audit completed",
        ]),
        version=1,
        approved=True,
    )
    repo.create_procedure(procedure, project.id)
    summary["created"].append("1 Procedure: Deployment Checklist")

    return summary


def seed_tenant(tenant_id: str) -> dict:
    """Seed a specific tenant with demo data."""
    bootstrap_schema(tenant_id)
    repo = GraphRepository(tenant_id)

    if tenant_id == "tenant_alpha":
        return seed_tenant_alpha(repo)
    elif tenant_id == "tenant_beta":
        return seed_tenant_beta(repo)
    else:
        return {"error": f"No seed data defined for tenant: {tenant_id}"}


def seed_all():
    """Seed all demo tenants."""
    if not check_connection():
        print("❌ FalkorDB is not available!")
        print("   Start it with: docker run -p 6379:6379 falkordb/falkordb")
        return

    print("🌱 Seeding MemoryMesh demo data...")

    for tenant in ["tenant_alpha", "tenant_beta"]:
        print(f"\n📦 Seeding {tenant}...")
        result = seed_tenant(tenant)
        for item in result.get("created", []):
            print(f"   ✅ {item}")

    print("\n✨ Seeding complete!")


if __name__ == "__main__":
    seed_all()
