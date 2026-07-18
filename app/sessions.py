"""In-memory web session store with background ADK turns."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from . import agent_bridge, docs_service
from .config import MAX_MESSAGE_LENGTH
from .schemas import PipelineStepOut, SessionStateResponse
from .security import (
    SecurityError,
    sanitize_error_message,
    validate_message_text,
    validate_workspace_name,
)

PhaseStr = str  # idle | thinking | generating | complete | error


class ConflictError(Exception):
    """Turn already in flight."""


@dataclass
class WebSession:
    id: str
    runner: Runner
    session_service: InMemorySessionService
    adk_session_id: str
    phase: PhaseStr = "idle"
    workspace: Optional[str] = None
    last_assistant: Optional[str] = None
    last_user: Optional[str] = None
    error: Optional[str] = None
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    turn_task: Optional[asyncio.Task] = None
    generation: int = 0  # bumped on reset to ignore stale turn results


def _busy(ws: WebSession) -> bool:
    return ws.turn_task is not None and not ws.turn_task.done()


def effective_phase(ws: WebSession) -> PhaseStr:
    if ws.phase == "error":
        return "error"
    if ws.workspace and docs_service.all_docs_ready(ws.workspace) and not _busy(ws):
        return "complete"
    if _busy(ws):
        if ws.workspace and docs_service.docs_count(ws.workspace) > 0:
            return "generating"
        if ws.workspace:
            return "generating"
        return "thinking"
    if ws.workspace and docs_service.all_docs_ready(ws.workspace):
        return "complete"
    return "idle"


def session_response(ws: WebSession) -> SessionStateResponse:
    pipeline = [
        PipelineStepOut(id=s.id, label=s.label, status=s.status)  # type: ignore[arg-type]
        for s in docs_service.pipeline_status(ws.workspace)
    ]
    phase = effective_phase(ws)
    if not _busy(ws) and phase != "error":
        ws.phase = phase
    return SessionStateResponse(
        session_id=ws.id,
        phase=phase,  # type: ignore[arg-type]
        workspace=ws.workspace,
        last_assistant=ws.last_assistant,
        last_user=ws.last_user,
        error=ws.error,
        docs_count=docs_service.docs_count(ws.workspace),
        pipeline=pipeline,
    )


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, WebSession] = {}
        self._store_lock = asyncio.Lock()

    async def create(self) -> WebSession:
        runner, session_service, adk_id = await agent_bridge.create_adk_session()
        sid = uuid.uuid4().hex
        ws = WebSession(
            id=sid,
            runner=runner,
            session_service=session_service,
            adk_session_id=adk_id,
        )
        async with self._store_lock:
            self._sessions[sid] = ws
        return ws

    def get(self, session_id: str) -> Optional[WebSession]:
        return self._sessions.get(session_id)

    async def reset(self, session_id: str) -> WebSession:
        existing = self._sessions.get(session_id)
        if existing is None:
            raise KeyError(session_id)
        existing.generation += 1
        if existing.turn_task and not existing.turn_task.done():
            existing.turn_task.cancel()
        runner, session_service, adk_id = await agent_bridge.create_adk_session()
        existing.runner = runner
        existing.session_service = session_service
        existing.adk_session_id = adk_id
        existing.phase = "idle"
        existing.workspace = None
        existing.last_assistant = None
        existing.last_user = None
        existing.error = None
        existing.turn_task = None
        return existing

    async def enqueue_message(self, session_id: str, text: str) -> None:
        ws = self._sessions.get(session_id)
        if ws is None:
            raise KeyError(session_id)
        cleaned = validate_message_text(text, max_length=MAX_MESSAGE_LENGTH)
        if ws.turn_lock.locked() or _busy(ws):
            raise ConflictError("A turn is already in progress.")
        ws.last_user = cleaned
        ws.error = None
        ws.phase = "thinking"
        gen = ws.generation
        ws.turn_task = asyncio.create_task(self._run_turn(ws, cleaned, gen))

    async def _refresh_workspace(self, ws: WebSession) -> None:
        workspace = await agent_bridge.read_workspace_from_session(
            ws.session_service, ws.adk_session_id
        )
        if not workspace:
            return
        try:
            ws.workspace = validate_workspace_name(workspace)
        except SecurityError:
            return

    async def _run_turn(self, ws: WebSession, text: str, generation: int) -> None:
        async with ws.turn_lock:
            if generation != ws.generation:
                return

            stop = asyncio.Event()

            async def _poll_workspace() -> None:
                while not stop.is_set():
                    if generation != ws.generation:
                        return
                    await self._refresh_workspace(ws)
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=1.5)
                    except asyncio.TimeoutError:
                        continue

            poll_task = asyncio.create_task(_poll_workspace())
            try:
                reply = await agent_bridge.run_turn(
                    ws.runner, ws.adk_session_id, text
                )
                if generation != ws.generation:
                    return
                ws.last_assistant = reply
                await self._refresh_workspace(ws)
                if docs_service.all_docs_ready(ws.workspace):
                    ws.phase = "complete"
                else:
                    ws.phase = "idle"
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                if generation != ws.generation:
                    return
                ws.error = sanitize_error_message(exc)
                ws.phase = "error"
            finally:
                stop.set()
                try:
                    await poll_task
                except Exception:  # noqa: BLE001
                    pass


store = SessionStore()
