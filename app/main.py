"""FastAPI entrypoint: API routes + static UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import docs_service
from .config import STATIC_DIR
from .markdown_render import render_markdown
from .schemas import (
    CreateSessionResponse,
    DocContentResponse,
    DocsListResponse,
    FileEntryOut,
    MessageAcceptedResponse,
    MessageRequest,
    PipelineStepOut,
    ResetResponse,
    SessionStateResponse,
    WorkspaceOut,
    WorkspacesListResponse,
)
from .security import SecurityError
from .sessions import ConflictError, session_response, store

app = FastAPI(title="sysdesigninit", version="1.0.0")


def _session_or_404(session_id: str):
    ws = store.get(session_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return ws


@app.post("/api/sessions", response_model=CreateSessionResponse)
async def create_session() -> CreateSessionResponse:
    ws = await store.create()
    return CreateSessionResponse(session_id=ws.id, phase="idle")


@app.get("/api/sessions/{session_id}", response_model=SessionStateResponse)
async def get_session(session_id: str) -> SessionStateResponse:
    ws = _session_or_404(session_id)
    return session_response(ws)


@app.post(
    "/api/sessions/{session_id}/messages",
    response_model=MessageAcceptedResponse,
)
async def post_message(
    session_id: str, body: MessageRequest
) -> MessageAcceptedResponse:
    _session_or_404(session_id)
    try:
        await store.enqueue_message(session_id, body.text)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.") from None
    except SecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MessageAcceptedResponse(accepted=True)


@app.post("/api/sessions/{session_id}/reset", response_model=ResetResponse)
async def reset_session(session_id: str) -> ResetResponse:
    try:
        ws = await store.reset(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.") from None
    return ResetResponse(session_id=ws.id, phase="idle")


def _docs_list_response(workspace: str | None) -> DocsListResponse:
    if not workspace:
        return DocsListResponse(workspace=None, files=[], pipeline=[])
    files = [
        FileEntryOut(name=e.name, ready=e.ready)
        for e in docs_service.list_files(workspace)
    ]
    pipeline = [
        PipelineStepOut(id=s.id, label=s.label, status=s.status)  # type: ignore[arg-type]
        for s in docs_service.pipeline_status(workspace)
    ]
    return DocsListResponse(workspace=workspace, files=files, pipeline=pipeline)


@app.get("/api/sessions/{session_id}/docs", response_model=DocsListResponse)
async def session_docs(session_id: str) -> DocsListResponse:
    ws = _session_or_404(session_id)
    if not ws.workspace:
        return DocsListResponse(workspace=None, files=[], pipeline=[])
    try:
        return _docs_list_response(ws.workspace)
    except SecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/sessions/{session_id}/docs/{filename}",
    response_model=DocContentResponse,
)
async def session_doc(session_id: str, filename: str) -> DocContentResponse:
    ws = _session_or_404(session_id)
    if not ws.workspace:
        raise HTTPException(status_code=404, detail="No workspace for this session.")
    try:
        markdown = docs_service.read_markdown(ws.workspace, filename)
    except SecurityError:
        raise HTTPException(status_code=404, detail="Filename is not allowed.") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found.") from None
    return DocContentResponse(
        filename=filename,
        markdown=markdown,
        html=render_markdown(markdown),
    )


@app.get("/api/workspaces", response_model=WorkspacesListResponse)
async def list_workspaces() -> WorkspacesListResponse:
    items = [
        WorkspaceOut(name=w.name, problem=w.problem)
        for w in docs_service.list_workspaces()
    ]
    return WorkspacesListResponse(workspaces=items)


@app.get("/api/workspaces/{name}/docs", response_model=DocsListResponse)
async def workspace_docs(name: str) -> DocsListResponse:
    try:
        from .security import validate_workspace_name

        safe = validate_workspace_name(name)
        return _docs_list_response(safe)
    except SecurityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/api/workspaces/{name}/docs/{filename}",
    response_model=DocContentResponse,
)
async def workspace_doc(name: str, filename: str) -> DocContentResponse:
    try:
        markdown = docs_service.read_markdown(name, filename)
    except SecurityError:
        raise HTTPException(status_code=404, detail="Not found.") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found.") from None
    return DocContentResponse(
        filename=filename,
        markdown=markdown,
        html=render_markdown(markdown),
    )


@app.get("/api/workspaces/{name}/download")
async def workspace_download(name: str) -> Response:
    try:
        data = docs_service.build_workspace_zip(name)
        from .security import validate_workspace_name

        safe = validate_workspace_name(name)
    except SecurityError:
        raise HTTPException(status_code=404, detail="Not found.") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found.") from None
    headers = {
        "Content-Disposition": f'attachment; filename="{safe}.zip"',
    }
    return Response(content=data, media_type="application/zip", headers=headers)


@app.get("/")
async def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="UI not built.")
    return FileResponse(index_path)


# Mount static assets (css/, js/). HTML is also under static/ but "/" is explicit.
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
