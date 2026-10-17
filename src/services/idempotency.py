"""Idempotency management for MemoryMesh chat orchestration.

Guarantees:
- Duplicate requests return the exact previous response without repeating side effects.
- Conflicting payloads with the same key are rejected with an explicit conflict error.
- Concurrent requests with the same key are detected and blocked from duplicate execution.
- Failed attempts can be safely retried.
"""

from __future__ import annotations
import hashlib
import json
import logging
from typing import Optional, Tuple, Any

from datetime import datetime, timezone
from src.config import settings
from src.db.repository import GraphRepository
from src.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


class IdempotencyError(Exception):
    """Base exception for idempotency violations."""
    pass


class IdempotencyConflictError(IdempotencyError):
    """Raised when the same key is reused with a different payload."""
    pass


class IdempotencyConcurrentError(IdempotencyError):
    """Raised when a request with the same key is currently running."""
    pass


def compute_payload_hash(request: ChatRequest) -> str:
    """Compute a deterministic hash of the request payload."""
    norm = f"{request.tenant_id.strip()}:{request.project_id.strip()}:{request.session_id.strip()}:{request.message.strip()}"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def check_or_reserve_idempotency(
    repo: GraphRepository,
    request: ChatRequest,
) -> Tuple[str, Optional[ChatResponse]]:
    """Check existing idempotency state or reserve execution atomically.

    Returns:
        ("completed", cached_response) if already completed successfully.
        ("reserved", None) if key was reserved for this new execution.

    Raises:
        IdempotencyConflictError if key was used with a different request payload.
        IdempotencyConcurrentError if request is currently being processed.
    """
    key = request.idempotency_key
    if not key:
        return "none", None

    payload_hash = compute_payload_hash(request)

    if not request.reservation_token:
        import uuid
        request.reservation_token = uuid.uuid4().hex

    # Atomically reserve or retrieve existing record
    try:
        existing, is_new = repo.create_idempotency_record(
            key=key,
            tenant_id=request.tenant_id,
            project_id=request.project_id or "",
            payload_hash=payload_hash,
            reservation_token=request.reservation_token,
        )
    except TypeError:
        existing, is_new = repo.create_idempotency_record(
            key=key,
            tenant_id=request.tenant_id,
            project_id=request.project_id or "",
            payload_hash=payload_hash,
        )

    if is_new:
        return "reserved", None

    # Record already exists
    existing_hash = existing.get("payload_hash", "")
    if existing_hash and existing_hash != payload_hash:
        raise IdempotencyConflictError(
            f"Idempotency key '{key}' was previously used with a different request payload."
        )

    status = existing.get("status", "")
    if status == "completed":
        response_json = existing.get("response_json", "")
        if response_json:
            try:
                data = json.loads(response_json)
                logger.info(f"Returning cached idempotent response for key: {key}")
                return "completed", ChatResponse.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to deserialized cached response for key {key}: {e}")

    elif status == "running":
        # Check for abandoned reservation timeout
        ts_str = existing.get("updated_at") or existing.get("created_at")
        is_abandoned = False
        if ts_str:
            try:
                created_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - created_dt).total_seconds()
                if age > settings.IDEMPOTENCY_TIMEOUT_SECONDS:
                    is_abandoned = True
                    logger.warning(
                        f"Idempotency reservation for key '{key}' has been running for {age:.1f}s "
                        f"(exceeds {settings.IDEMPOTENCY_TIMEOUT_SECONDS}s timeout). "
                        f"Recovering abandoned reservation for safe retry."
                    )
            except Exception as e:
                logger.debug(f"Timestamp parse error for key {key}: {e}")

        if is_abandoned:
            import uuid
            request.reservation_token = uuid.uuid4().hex
            recover_fn = getattr(repo, "recover_idempotency_record", None)
            if callable(recover_fn):
                recover_fn(
                    key=key,
                    reservation_token=request.reservation_token,
                    error="Recovered from abandoned state",
                )
            else:
                repo.complete_idempotency_record(
                    key, status="running", reservation_token=request.reservation_token, error="Recovered from abandoned state"
                )
            return "reserved", None

        raise IdempotencyConcurrentError(
            f"A request with idempotency key '{key}' is currently being processed."
        )

    # If previous execution failed, allow safe retry by setting status to running
    logger.info(f"Retrying previously failed request for key: {key}")
    import uuid
    request.reservation_token = uuid.uuid4().hex
    retry_fn = getattr(repo, "retry_failed_idempotency_record", None)
    if callable(retry_fn):
        retry_fn(key=key, reservation_token=request.reservation_token)
    else:
        repo.complete_idempotency_record(
            key, status="running", reservation_token=request.reservation_token, error=""
        )
    return "reserved", None


def finalize_idempotency_success(
    repo: GraphRepository,
    key: Optional[str],
    response: Any,
    reservation_token: Optional[str] = None,
) -> bool:
    """Mark the idempotency key as completed and store the response."""
    if not key:
        return True
    if not reservation_token:
        logger.warning(f"finalize_idempotency_success called for key '{key}' without reservation_token. Write rejected.")
        return False
    try:
        if isinstance(response, ChatResponse):
            resp_json = response.model_dump_json()
        elif isinstance(response, dict):
            resp_json = json.dumps(response)
        else:
            resp_json = str(response)
        res = repo.complete_idempotency_record(
            key=key,
            status="completed",
            response_json=resp_json,
            reservation_token=reservation_token,
        )
        if not res:
            logger.warning(
                f"Idempotency completion rejected for key '{key}' with token '{reservation_token}'. "
                f"Reservation was either revoked, timed out, or already completed."
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to record idempotency completion for key {key}: {e}")
        return False


def finalize_idempotency_failure(
    repo: GraphRepository,
    key: Optional[str],
    error_message: str,
    reservation_token: Optional[str] = None,
) -> bool:
    """Mark the idempotency key as failed so it can be retried safely."""
    if not key:
        return True
    if not reservation_token:
        logger.warning(f"finalize_idempotency_failure called for key '{key}' without reservation_token. Write rejected.")
        return False
    try:
        res = repo.complete_idempotency_record(
            key=key,
            status="failed",
            error=error_message,
            reservation_token=reservation_token,
        )
        if not res:
            logger.warning(
                f"Idempotency failure rejected for key '{key}' with token '{reservation_token}'. "
                f"Reservation was already revoked or completed."
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to record idempotency failure for key {key}: {e}")
        return False
