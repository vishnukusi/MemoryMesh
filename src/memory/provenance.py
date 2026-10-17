"""Provenance tracking — links records to their source evidence."""

from __future__ import annotations
from src.db.repository import GraphRepository


def get_fact_provenance(repo: GraphRepository, fact_id: str) -> dict:
    """Get a fact and its supporting episode(s)."""
    fact = repo.get_fact_with_evidence(fact_id)
    if not fact:
        return {"error": "Fact not found"}
    return fact


def get_decision_provenance(repo: GraphRepository, decision_id: str) -> dict:
    """Get a decision with its supporting evidence."""
    return repo.get_decision_with_evidence(decision_id)
