"""Memory retrieval — handles querying stored memories."""

from __future__ import annotations
from src.db.repository import GraphRepository


def retrieve_session_history(repo: GraphRepository, session_id: str) -> list[dict]:
    """Retrieve all episodes from a specific session."""
    return repo.get_episodes_by_session(session_id)


def retrieve_project_memory(repo: GraphRepository, project_id: str) -> dict:
    """Retrieve comprehensive project memory including facts, decisions, tasks."""
    return {
        "facts": repo.get_facts_by_project(project_id),
        "decisions": repo.get_decisions_by_project(project_id),
        "tasks": repo.get_tasks_by_project(project_id),
        "procedures": repo.get_procedures_by_project(project_id),
        "recent_episodes": repo.get_episodes_by_project(project_id, limit=20),
    }


def search_memory(repo: GraphRepository, project_id: str, query: str) -> dict:
    """Search across all memory types, scoped to the specified project."""
    return {
        "facts": repo.search_facts(query, project_id=project_id, limit=10),
        "decisions": repo.search_decisions(query, project_id=project_id, limit=10),
        "tasks": repo.search_tasks(query, project_id=project_id),
        "episodes": repo.search_episodes(project_id, query, limit=10),
        "procedures": repo.search_procedures(query, project_id=project_id, limit=5),
    }
