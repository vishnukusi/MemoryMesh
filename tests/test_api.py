"""Tests for the FastAPI API endpoints."""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from src.api.main import app
from src.db.connection import check_connection

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="FalkorDB not available"
)

client = TestClient(app)


def test_health_endpoint():
    """Health endpoint should return structured status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "falkordb" in data
    assert "ollama" in data
    assert "tenants" in data


def test_api_health_endpoint():
    """API health endpoint should also work."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_invalid_tenant_rejected():
    """Requests with invalid tenant IDs should be rejected."""
    response = client.get("/api/projects", params={"tenant_id": "evil"})
    assert response.status_code == 403


def test_get_projects():
    """Projects endpoint should return a list."""
    response = client.get("/api/projects", params={"tenant_id": "tenant_alpha"})
    assert response.status_code == 200
    data = response.json()
    assert "projects" in data


def test_chat_empty_message():
    """Chat with empty message should fail."""
    response = client.post("/api/chat", json={
        "message": "",
        "session_id": "test",
        "project_id": "test",
        "tenant_id": "tenant_alpha",
    })
    assert response.status_code == 400


def test_get_handoffs():
    """Handoffs endpoint should return a list."""
    response = client.get("/api/handoffs", params={"tenant_id": "tenant_alpha"})
    assert response.status_code == 200
    data = response.json()
    assert "handoffs" in data


def test_get_runs():
    """Runs endpoint should return a list."""
    response = client.get("/api/runs", params={"tenant_id": "tenant_alpha"})
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data


def test_graph_stats():
    """Graph stats endpoint should return node and relationship counts."""
    response = client.get("/api/graph/stats", params={"tenant_id": "tenant_alpha"})
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "relationships" in data


def test_seed_endpoint():
    """Seed endpoint should populate demo data."""
    response = client.post("/api/seed", params={"tenant_id": "tenant_alpha"})
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "seeded"
