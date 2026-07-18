"""Pydantic request/response models for the web API."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Phase = Literal["idle", "thinking", "generating", "complete", "error"]
PipelineStatus = Literal["pending", "ready"]
ActivityKind = Literal["file_ready", "info"]
ChatRole = Literal["user", "assistant"]


class CreateSessionResponse(BaseModel):
    session_id: str
    phase: Phase = "idle"


class MessageRequest(BaseModel):
    text: str = Field(..., min_length=1)


class MessageAcceptedResponse(BaseModel):
    accepted: bool = True


class PipelineStepOut(BaseModel):
    id: str
    label: str
    status: PipelineStatus


class CurrentStepOut(BaseModel):
    id: str
    label: str


class ActivityEventOut(BaseModel):
    ts: float
    kind: ActivityKind
    filename: Optional[str] = None
    message: str


class ChatMessageOut(BaseModel):
    role: ChatRole
    text: str
    ts: Optional[float] = None


class BriefOut(BaseModel):
    problem: Optional[str] = None
    critical_flows: Optional[str] = None
    scale: Optional[str] = None
    quality_targets: Optional[str] = None
    constraints: Optional[str] = None
    maturity: Optional[str] = None
    must_haves: Optional[str] = None
    out_of_scope: Optional[str] = None
    reasoning: Optional[str] = None


class SessionStateResponse(BaseModel):
    session_id: str
    phase: Phase
    workspace: Optional[str] = None
    problem: Optional[str] = None
    last_assistant: Optional[str] = None
    last_user: Optional[str] = None
    error: Optional[str] = None
    status_message: Optional[str] = None
    docs_count: int = 0
    docs_total: int = 12
    elapsed_ms: Optional[int] = None
    current_step: Optional[CurrentStepOut] = None
    activity: List[ActivityEventOut] = Field(default_factory=list)
    just_completed: bool = False
    pipeline: List[PipelineStepOut] = Field(default_factory=list)
    messages: List[ChatMessageOut] = Field(default_factory=list)
    design_context: Optional[str] = None
    brief: Optional[BriefOut] = None
    overwrite_warning: Optional[str] = None


class FileEntryOut(BaseModel):
    name: str
    ready: bool


class DocsListResponse(BaseModel):
    workspace: Optional[str] = None
    files: List[FileEntryOut] = Field(default_factory=list)
    pipeline: List[PipelineStepOut] = Field(default_factory=list)


class TocEntryOut(BaseModel):
    id: str
    text: str
    level: int


class DocContentResponse(BaseModel):
    filename: str
    markdown: str
    html: str
    toc: List[TocEntryOut] = Field(default_factory=list)


class WorkspaceOut(BaseModel):
    name: str
    problem: Optional[str] = None
    mtime: Optional[float] = None
    docs_count: int = 0


class WorkspacesListResponse(BaseModel):
    workspaces: List[WorkspaceOut] = Field(default_factory=list)


class ChatHistoryResponse(BaseModel):
    workspace: str
    messages: List[ChatMessageOut] = Field(default_factory=list)


class ResetResponse(BaseModel):
    session_id: str
    phase: Phase = "idle"


class AckCompleteResponse(BaseModel):
    ok: bool = True


class CancelResponse(BaseModel):
    session_id: str
    phase: Phase
    status_message: Optional[str] = None
