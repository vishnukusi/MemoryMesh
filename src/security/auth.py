"""Tenant authorization and API authentication layer for MemoryMesh.

Supports:
- Configurable authentication via API keys per tenant or master admin key.
- Explicit development mode where authentication can be disabled for local development,
  while still strictly enforcing tenant boundary allowlists.
- Fast, secure constant-time comparison to prevent timing attacks.
"""

from __future__ import annotations
import hmac
import logging
from typing import Optional

from fastapi import Header, HTTPException, Query, Security, Depends
from fastapi.security import APIKeyHeader

from src.config import settings
from src.memory.tenant_scope import validate_tenant

logger = logging.getLogger(__name__)

api_key_header_scheme = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


def _secure_compare(val1: str, val2: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    if not val1 or not val2:
        return False
    return hmac.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))


def is_authorized_tenant(tenant_id: str, api_key: Optional[str] = None) -> tuple[bool, str]:
    """Check if the provided api_key is authorized for tenant_id.

    Returns:
        (is_authorized: bool, error_reason: str)
    """
    if not validate_tenant(tenant_id):
        return False, f"Unknown or disallowed tenant: '{tenant_id}'"

    # If auth is disabled (e.g. local development mode), allow verified tenants
    if not settings.AUTH_ENABLED:
        return True, ""

    if not api_key:
        return False, f"Missing required API key header ({settings.API_KEY_HEADER})"

    # Check master key
    if settings.MASTER_API_KEY and _secure_compare(api_key, settings.MASTER_API_KEY):
        return True, ""

    # Check tenant-specific key
    expected_key = settings.TENANT_KEYS.get(tenant_id)
    if expected_key and _secure_compare(api_key, expected_key):
        return True, ""

    return False, f"Provided API key is not authorized for tenant '{tenant_id}'"


def is_authorized_admin(api_key: Optional[str] = None) -> tuple[bool, str]:
    """Check if the provided api_key has administrative privileges (Master Key)."""
    if not settings.AUTH_ENABLED and settings.DEV_MODE:
        return True, ""
    if not api_key:
        return False, f"Missing required admin API key header ({settings.API_KEY_HEADER})"
    if settings.MASTER_API_KEY and _secure_compare(api_key, settings.MASTER_API_KEY):
        return True, ""
    return False, "Administrative operations require a valid Master API Key"


async def verify_tenant_access(
    tenant_id: str,
    api_key: Optional[str] = Security(api_key_header_scheme),
) -> str:
    """FastAPI dependency to authorize access to a specific tenant.

    Raises HTTPException (401 or 403) on unauthorized requests.
    Returns the validated tenant_id.
    """
    authorized, reason = is_authorized_tenant(tenant_id, api_key)
    if not authorized:
        if not api_key and settings.AUTH_ENABLED:
            logger.warning(f"Unauthorized tenant request: {reason}")
            raise HTTPException(status_code=401, detail=reason)
        logger.warning(f"Forbidden tenant request for '{tenant_id}': {reason}")
        raise HTTPException(status_code=403, detail=reason)

    return tenant_id
