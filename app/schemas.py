"""Pydantic request/response models for the web API."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Phase = Literal["idle", "thinking", "generating", "complete", "error"]
PipelineStatus = Literal["pending", "ready"]


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


class SessionStateResponse(BaseModel):
    session_id: str
    phase: Phase
    workspace: Optional[str] = None
    last_assistant: Optional[str] = None
    last_user: Optional[str] = None
    error: Optional[str] = None
    docs_count: int = 0
    pipeline: List[PipelineStepOut] = Field(default_factory=list)


class FileEntryOut(BaseModel):
    name: str
    ready: bool


class DocsListResponse(BaseModel):
    workspace: Optional[str] = None
    files: List[FileEntryOut] = Field(default_factory=list)
    pipeline: List[PipelineStepOut] = Field(default_factory=list)


class DocContentResponse(BaseModel):
    filename: str
    markdown: str
    html: str


class WorkspaceOut(BaseModel):
    name: str
    problem: Optional[str] = None


class WorkspacesListResponse(BaseModel):
    workspaces: List[WorkspaceOut] = Field(default_factory=list)


class ResetResponse(BaseModel):
    session_id: str
    phase: Phase = "idle"
