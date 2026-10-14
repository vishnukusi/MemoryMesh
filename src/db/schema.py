"""FalkorDB graph schema bootstrap and index creation."""

from __future__ import annotations
import logging
from falkordb import Graph

from src.db.connection import get_graph

logger = logging.getLogger(__name__)


def bootstrap_schema(tenant_id: str) -> None:
    """Create indexes for the tenant graph.
    
    Safe to call multiple times — FalkorDB CREATE INDEX is idempotent
    when the index already exists.
    """
    graph = get_graph(tenant_id)

    # Node range indexes for fast lookups
    _safe_create_index(graph, "Project", "id")
    _safe_create_index(graph, "Project", "name")
    _safe_create_index(graph, "Person", "id")
    _safe_create_index(graph, "Person", "name")
    _safe_create_index(graph, "Episode", "id")
    _safe_create_index(graph, "Episode", "session_id")
    _safe_create_index(graph, "Episode", "project_id")
    _safe_create_index(graph, "Episode", "timestamp")
    _safe_create_index(graph, "Fact", "id")
    _safe_create_index(graph, "Fact", "subject")
    _safe_create_index(graph, "Fact", "status")
    _safe_create_index(graph, "Fact", "project_id")
    _safe_create_index(graph, "Decision", "id")
    _safe_create_index(graph, "Decision", "title")
    _safe_create_index(graph, "Decision", "project_id")
    _safe_create_index(graph, "Task", "id")
    _safe_create_index(graph, "Task", "title")
    _safe_create_index(graph, "Task", "status")
    _safe_create_index(graph, "Task", "project_id")
    _safe_create_index(graph, "Procedure", "id")
    _safe_create_index(graph, "Procedure", "title")
    _safe_create_index(graph, "Procedure", "project_id")
    _safe_create_index(graph, "AgentRun", "id")
    _safe_create_index(graph, "Handoff", "id")
    _safe_create_index(graph, "Handoff", "status")
    _safe_create_index(graph, "IdempotencyRecord", "key")
    _safe_create_index(graph, "IdempotencyRecord", "reservation_token")

    # Explicit migration for legacy records missing reservation_token
    _migrate_legacy_idempotency_records(graph)

    logger.info(f"Schema bootstrapped for tenant: {tenant_id}")


def _safe_create_index(graph: Graph, label: str, prop: str) -> None:
    """Create a range index, ignoring if it already exists."""
    try:
        graph.create_node_range_index(label, prop)
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg or "exists" in msg or "equivalent" in msg:
            pass  # Index already exists — fine
        else:
            logger.warning(f"Index creation failed for {label}.{prop}: {e}")


def _migrate_legacy_idempotency_records(graph: Graph) -> None:
    """Explicitly assign tokens to legacy idempotency records without bypassing checks."""
    try:
        graph.query("""
        MATCH (k:IdempotencyRecord)
        WHERE k.reservation_token IS NULL
        SET k.reservation_token = 'legacy-' + k.key
        """)
    except Exception as e:
        logger.debug(f"Legacy idempotency migration notice: {e}")
