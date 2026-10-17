"""FalkorDB connection management.

Provides a thread-safe connection pool to FalkorDB.
The FalkorDB Python client uses synchronous Redis under the hood,
so we wrap calls in asyncio.to_thread() when used from async FastAPI endpoints.
"""

from __future__ import annotations
import logging
from typing import Optional
from falkordb import FalkorDB, Graph

from src.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton
_db_instance: Optional[FalkorDB] = None


def get_db() -> FalkorDB:
    """Return a FalkorDB client instance (lazy singleton)."""
    global _db_instance
    if _db_instance is None:
        _db_instance = FalkorDB(
            host=settings.FALKORDB_HOST,
            port=settings.FALKORDB_PORT,
        )
    return _db_instance


def get_graph(tenant_id: str) -> Graph:
    """Get the FalkorDB graph for a validated tenant.

    Raises ValueError for invalid tenant IDs.
    """
    graph_name = settings.get_graph_name(tenant_id)
    db = get_db()
    return db.select_graph(graph_name)


def check_connection() -> bool:
    """Check if FalkorDB is reachable."""
    try:
        db = get_db()
        db.list_graphs()
        return True
    except Exception as e:
        logger.warning(f"FalkorDB connection failed: {e}")
        return False


def close_connection():
    """Close the FalkorDB connection."""
    global _db_instance
    if _db_instance is not None:
        try:
            _db_instance.close()
        except Exception:
            pass
        _db_instance = None
