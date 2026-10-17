"""Tenant scope — validates and manages tenant access."""

from __future__ import annotations
from src.config import settings


def validate_tenant(tenant_id: str) -> bool:
    """Check if a tenant ID is in the allowlist."""
    return tenant_id in settings.ALLOWED_TENANTS


def get_allowed_tenants() -> list[str]:
    """Return the list of allowed tenants."""
    return list(settings.ALLOWED_TENANTS)
