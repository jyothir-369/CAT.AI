"""
Shared Pydantic schemas — canonical type definitions used by both
the API and the Celery worker. Import from here, not from db/models/.

These are transport/service-layer types, not ORM models.
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserSchema(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime


class TokenSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Conversation ──────────────────────────────────────────────────────────────

class MessageSchema(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    tokens_in: int = 0
    tokens_out: int = 0
    model_id: Optional[str] = None
    created_at: datetime


class ConversationSchema(BaseModel):
    id: str
    org_id: str
    user_id: str
    title: Optional[str] = None
    model_id: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequestSchema(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = None
    kb_id: Optional[str] = None
    use_memory: bool = True


class StreamChunkSchema(BaseModel):
    token: Optional[str] = None
    done: Optional[bool] = None
    conversation_id: Optional[str] = None
    error: Optional[str] = None


# ── Knowledge ─────────────────────────────────────────────────────────────────

class KnowledgeBaseSchema(BaseModel):
    id: str
    org_id: str
    name: str
    description: Optional[str] = None
    embedding_model: str
    chunk_strategy: str
    doc_count: int = 0
    created_at: datetime


class DocumentChunkSchema(BaseModel):
    id: str
    document_id: str
    kb_id: str
    content: str
    chunk_index: int
    token_count: int


# ── Workflow ──────────────────────────────────────────────────────────────────

class WorkflowStepSchema(BaseModel):
    id: str
    type: str
    config: dict[str, Any] = {}
    inputs: dict[str, Any] = {}
    outputs: dict[str, Any] = {}


class WorkflowEdgeSchema(BaseModel):
    from_: str
    to: str
    condition: Optional[str] = None


class WorkflowDefinitionSchema(BaseModel):
    steps: list[WorkflowStepSchema] = []
    edges: list[WorkflowEdgeSchema] = []


class WorkflowSchema(BaseModel):
    id: str
    org_id: str
    name: str
    description: Optional[str] = None
    trigger: dict[str, Any]
    is_active: bool
    created_at: datetime


class WorkflowRunSchema(BaseModel):
    id: str
    workflow_id: str
    version: int
    trigger_type: str
    status: str
    context: dict[str, Any] = {}
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


# ── Memory ────────────────────────────────────────────────────────────────────

class MemorySchema(BaseModel):
    id: str
    org_id: str
    user_id: str
    content: str
    importance_score: float = 1.0
    created_at: datetime


# ── Billing ───────────────────────────────────────────────────────────────────

class UsageRecordSchema(BaseModel):
    org_id: str
    user_id: str
    resource_type: str
    model_id: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: Optional[int] = None


# ── Tool ──────────────────────────────────────────────────────────────────────

class ToolCallSchema(BaseModel):
    tool_name: str
    args: dict[str, Any]


class ToolResultSchema(BaseModel):
    tool_name: str
    output: dict[str, Any]
    success: bool
    duration_ms: Optional[int] = None