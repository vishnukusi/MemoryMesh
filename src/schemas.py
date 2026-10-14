"""Data schemas and Pydantic models for MemoryMesh.

Defines graph node representations, API contracts, and extraction structures.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


def new_id() -> str:
    """Generate a unique random ID."""
    return str(uuid.uuid4())


def utc_now_iso() -> str:
    """Return the current UTC timestamp formatted as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ─── Enumerations ────────────────────────────────────────────────

class FactStatus(str, Enum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    DISPUTED = "disputed"
    CANDIDATE = "candidate"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class HandoffStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    FAILED = "failed"


# ─── Graph Node Models ──────────────────────────────────────────

class ProjectNode(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    description: Optional[str] = ""
    status: str = "active"
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


# Alias for convenience and backward compatibility
Project = ProjectNode


class PersonNode(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    role: Optional[str] = ""
    email: Optional[str] = None
    created_at: str = Field(default_factory=utc_now_iso)


class EpisodeNode(BaseModel):
    id: str = Field(default_factory=new_id)
    session_id: str
    project_id: Optional[str] = ""
    content: str
    actor: str = "user"
    event_type: str = "message"
    scope: Optional[str] = ""
    timestamp: str = Field(default_factory=utc_now_iso)
    source_event_id: Optional[str] = None


class FactNode(BaseModel):
    id: str = Field(default_factory=new_id)
    subject: str
    predicate: str
    value: str
    confidence: float = 1.0
    status: str = FactStatus.CURRENT.value
    project_id: Optional[str] = ""
    valid_from: str = Field(default_factory=utc_now_iso)
    valid_to: Optional[str] = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    version: int = 1
    source_episode_id: Optional[str] = None


class DecisionNode(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    chosen_option: str
    rationale: Optional[str] = ""
    status: str = "active"
    project_id: Optional[str] = ""
    decided_at: str = Field(default_factory=utc_now_iso)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    source_episode_id: Optional[str] = None


class TaskNode(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    description: Optional[str] = ""
    status: str = TaskStatus.PENDING.value
    priority: str = "medium"
    owner_id: Optional[str] = None
    project_id: Optional[str] = ""
    revision: int = 1
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class ProcedureNode(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    description: Optional[str] = ""
    project_id: Optional[str] = ""
    steps_json: str = "[]"
    version: int = 1
    approved: bool = False
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class AgentRunNode(BaseModel):
    id: str = Field(default_factory=new_id)
    agent_name: str
    goal: str
    status: str = "running"
    summary: Optional[str] = ""
    error: Optional[str] = None
    started_at: str = Field(default_factory=utc_now_iso)
    completed_at: Optional[str] = None


class HandoffNode(BaseModel):
    id: str = Field(default_factory=new_id)
    from_agent: str
    to_agent: str
    task_id: Optional[str] = None
    context_summary: str = ""
    status: str = HandoffStatus.PENDING.value
    created_at: str = Field(default_factory=utc_now_iso)
    claimed_at: Optional[str] = None
    completed_at: Optional[str] = None


# ─── Curator Extraction Models ──────────────────────────────────

class ExtractedFact(BaseModel):
    subject: str
    predicate: str
    value: str
    confidence: float = 1.0


class ExtractedDecision(BaseModel):
    title: str
    chosen_option: str
    rationale: Optional[str] = ""


class ExtractedTask(BaseModel):
    title: str
    description: Optional[str] = ""
    status: str = "pending"
    blocked_by: Optional[List[str]] = Field(default_factory=list)


class ExtractedProcedure(BaseModel):
    title: str
    description: Optional[str] = ""
    steps: List[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    facts: List[ExtractedFact] = Field(default_factory=list)
    decisions: List[ExtractedDecision] = Field(default_factory=list)
    tasks: List[ExtractedTask] = Field(default_factory=list)
    procedures: List[ExtractedProcedure] = Field(default_factory=list)
    task_updates: List[Dict[str, Any]] = Field(default_factory=list)


# ─── Investigator & Planner Models ──────────────────────────────

class InvestigationResult(BaseModel):
    relevant_facts: List[Dict[str, Any]] = Field(default_factory=list)
    relevant_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    relevant_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    relevant_episodes: List[Dict[str, Any]] = Field(default_factory=list)
    relevant_procedures: List[Dict[str, Any]] = Field(default_factory=list)
    blockers: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0


class PlannerAction(BaseModel):
    recommendation: str = ""
    action_type: str = "none"  # "none", "update_task", "create_handoff", "recommend"
    target_task_id: Optional[str] = None
    new_status: Optional[str] = None
    handoff_to: Optional[str] = None
    reasoning: str = ""


# ─── Verifier & Evidence Models ─────────────────────────────────

class EvidenceRef(BaseModel):
    node_type: str
    node_id: str
    summary: str = ""
    confidence: float = 1.0


class VerificationResult(BaseModel):
    is_valid: bool = True
    final_answer: str = ""
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)


# ─── API & Orchestration Contracts ──────────────────────────────

class AgentTraceSummary(BaseModel):
    agent_name: str
    goal: str
    status: str
    records_written: Optional[List[str]] = Field(default_factory=list)
    records_read: Optional[List[str]] = Field(default_factory=list)
    duration_ms: Optional[int] = 0
    error: Optional[str] = None
    run_id: Optional[str] = None
    summary: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    session_id: str
    project_id: Optional[str] = "default"
    tenant_id: str = "tenant_alpha"
    idempotency_key: Optional[str] = None
    reservation_token: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    new_status: str
    tenant_id: str
    expected_revision: Optional[int] = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    request_id: Optional[str] = None
    project_id: Optional[str] = None
    tenant_id: Optional[str] = None
    evidence: Optional[List[EvidenceRef]] = Field(default_factory=list)
    agent_traces: Optional[List[AgentTraceSummary]] = Field(default_factory=list)
    handoff_created: Optional[str] = None
    status: str = "success"
    error: Optional[str] = None
    confidence: Optional[float] = 1.0


class HealthResponse(BaseModel):
    status: str
    falkordb: str
    ollama: str
    model: str
    tenants: List[str]
