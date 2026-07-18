"""In-memory web session store with background ADK turns."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from . import agent_bridge, chat_store, docs_service
from .brief_parse import parse_brief_sections
from .config import MAX_MESSAGE_LENGTH, PIPELINE_LABELS
from .schemas import (
    ActivityEventOut,
    BriefOut,
    ChatMessageOut,
    CurrentStepOut,
    PipelineStepOut,
    SessionStateResponse,
)
from .security import (
    SecurityError,
    sanitize_error_message,
    validate_message_text,
    validate_workspace_name,
)
from sys_des_in.tools.file_tools import PIPELINE_FILE_ORDER

PhaseStr = str
ACTIVITY_MAX = 30


class ConflictError(Exception):
    """Turn already in flight."""


@dataclass
class ActivityEvent:
    ts: float
    kind: str
    message: str
    filename: Optional[str] = None


@dataclass
class ChatMessage:
    role: str
    text: str
    ts: float = field(default_factory=time.time)


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
    status_message: Optional[str] = None
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    turn_task: Optional[asyncio.Task] = None
    generation: int = 0
    turn_started_at: Optional[float] = None
    activity: List[ActivityEvent] = field(default_factory=list)
    seen_files: set[str] = field(default_factory=set)
    just_completed: bool = False
    messages: List[ChatMessage] = field(default_factory=list)
    design_context: Optional[str] = None
    overwrite_warning: Optional[str] = None


def _busy(ws: WebSession) -> bool:
    return ws.turn_task is not None and not ws.turn_task.done()


def effective_phase(ws: WebSession) -> PhaseStr:
    if ws.phase == "error":
        return "error"
    if ws.workspace and docs_service.all_docs_ready(ws.workspace) and not _busy(ws):
        return "complete"
    if _busy(ws):
        if ws.workspace:
            return "generating"
        return "thinking"
    if ws.workspace and docs_service.all_docs_ready(ws.workspace):
        return "complete"
    return "idle"


def _push_activity(
    ws: WebSession,
    message: str,
    *,
    kind: str = "info",
    filename: Optional[str] = None,
) -> None:
    ws.activity.append(
        ActivityEvent(ts=time.time(), kind=kind, message=message, filename=filename)
    )
    if len(ws.activity) > ACTIVITY_MAX:
        ws.activity = ws.activity[-ACTIVITY_MAX:]


def _sync_file_activity(ws: WebSession) -> None:
    if not ws.workspace:
        return
    ready = docs_service.ready_filenames(ws.workspace)
    new_files = ready - ws.seen_files
    for name in PIPELINE_FILE_ORDER:
        if name in new_files:
            label = PIPELINE_LABELS.get(name, name)
            _push_activity(
                ws,
                f"{label} written",
                kind="file_ready",
                filename=name,
            )
    ws.seen_files |= ready


def _current_step(ws: WebSession, phase: PhaseStr) -> Optional[CurrentStepOut]:
    steps = docs_service.pipeline_status(ws.workspace)
    if not steps:
        return None
    if phase == "generating" or _busy(ws):
        for s in steps:
            if s.status == "pending":
                return CurrentStepOut(id=s.id, label=s.label)
        last = steps[-1]
        return CurrentStepOut(id=last.id, label=last.label)
    ready = [s for s in steps if s.status == "ready"]
    if ready:
        last = ready[-1]
        return CurrentStepOut(id=last.id, label=last.label)
    return None


def session_response(ws: WebSession) -> SessionStateResponse:
    pipeline = [
        PipelineStepOut(id=s.id, label=s.label, status=s.status)  # type: ignore[arg-type]
        for s in docs_service.pipeline_status(ws.workspace)
    ]
    phase = effective_phase(ws)
    prev_phase = ws.phase
    if not _busy(ws) and phase != "error":
        if phase == "complete" and prev_phase != "complete":
            ws.just_completed = True
            if ws.workspace:
                try:
                    chat_store.write_meta(
                        ws.workspace, docs_count=docs_service.docs_count(ws.workspace)
                    )
                except Exception:  # noqa: BLE001
                    pass
        ws.phase = phase

    elapsed: Optional[int] = None
    if ws.turn_started_at is not None and _busy(ws):
        elapsed = max(0, int((time.time() - ws.turn_started_at) * 1000))

    brief: Optional[BriefOut] = parse_brief_sections(ws.design_context)

    return SessionStateResponse(
        session_id=ws.id,
        phase=phase,  # type: ignore[arg-type]
        workspace=ws.workspace,
        problem=docs_service.read_problem(ws.workspace),
        last_assistant=ws.last_assistant,
        last_user=ws.last_user,
        error=ws.error,
        status_message=ws.status_message,
        docs_count=docs_service.docs_count(ws.workspace),
        docs_total=docs_service.docs_total(),
        elapsed_ms=elapsed,
        current_step=_current_step(ws, phase),
        activity=[
            ActivityEventOut(
                ts=a.ts,
                kind=a.kind,  # type: ignore[arg-type]
                filename=a.filename,
                message=a.message,
            )
            for a in ws.activity
        ],
        just_completed=ws.just_completed,
        pipeline=pipeline,
        messages=[
            ChatMessageOut(role=m.role, text=m.text, ts=m.ts)  # type: ignore[arg-type]
            for m in ws.messages
        ],
        design_context=ws.design_context,
        brief=brief,
        overwrite_warning=ws.overwrite_warning,
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
        existing.status_message = None
        existing.turn_task = None
        existing.turn_started_at = None
        existing.activity = []
        existing.seen_files = set()
        existing.just_completed = False
        existing.messages = []
        existing.design_context = None
        existing.overwrite_warning = None
        return existing

    async def ack_complete(self, session_id: str) -> None:
        ws = self._sessions.get(session_id)
        if ws is None:
            raise KeyError(session_id)
        ws.just_completed = False

    async def cancel(self, session_id: str) -> WebSession:
        ws = self._sessions.get(session_id)
        if ws is None:
            raise KeyError(session_id)
        if not _busy(ws):
            raise ConflictError("No turn is in progress.")
        ws.generation += 1
        if ws.turn_task and not ws.turn_task.done():
            ws.turn_task.cancel()
        ws.phase = "idle"
        ws.error = None
        ws.status_message = "Cancelled"
        ws.turn_started_at = None
        _push_activity(ws, "Generation cancelled")
        return ws

    async def enqueue_message(self, session_id: str, text: str) -> None:
        ws = self._sessions.get(session_id)
        if ws is None:
            raise KeyError(session_id)
        cleaned = validate_message_text(text, max_length=MAX_MESSAGE_LENGTH)
        if ws.turn_lock.locked() or _busy(ws):
            raise ConflictError("A turn is already in progress.")
        ws.last_user = cleaned
        ws.error = None
        ws.status_message = None
        ws.phase = "thinking"
        ws.turn_started_at = time.time()
        ws.just_completed = False
        ws.messages.append(ChatMessage(role="user", text=cleaned))
        gen = ws.generation
        ws.turn_task = asyncio.create_task(self._run_turn(ws, cleaned, gen))

    async def _refresh_state(self, ws: WebSession) -> None:
        keys = await agent_bridge.read_state_keys(
            ws.session_service, ws.adk_session_id
        )
        workspace = keys.get("workspace")
        if workspace:
            try:
                safe = validate_workspace_name(workspace)
                if ws.workspace != safe:
                    # Overwrite warning if folder already had docs
                    if docs_service.workspace_exists(safe) and docs_service.docs_count(safe) > 0:
                        ws.overwrite_warning = (
                            f"This will overwrite files in workspace “{safe}”."
                        )
                    ws.workspace = safe
                    # Hydrate chat from disk if memory empty beyond current turn
                    disk = chat_store.load_chat(safe)
                    if disk and len(ws.messages) <= 2:
                        # Keep in-memory as source of truth for active session;
                        # merge only if we have no assistant yet beyond last user
                        pass
            except SecurityError:
                pass
        ctx = keys.get("design_context")
        if isinstance(ctx, str) and ctx.strip():
            ws.design_context = ctx.strip()
        _sync_file_activity(ws)

    async def _run_turn(self, ws: WebSession, text: str, generation: int) -> None:
        async with ws.turn_lock:
            if generation != ws.generation:
                return

            stop = asyncio.Event()

            async def _poll_workspace() -> None:
                while not stop.is_set():
                    if generation != ws.generation:
                        return
                    await self._refresh_state(ws)
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=1.0)
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
                ws.messages.append(ChatMessage(role="assistant", text=reply))
                await self._refresh_state(ws)
                if ws.workspace:
                    try:
                        chat_store.append_turn(
                            ws.workspace,
                            user_text=text,
                            assistant_text=reply,
                        )
                    except Exception:  # noqa: BLE001
                        pass
                if docs_service.all_docs_ready(ws.workspace):
                    ws.phase = "complete"
                    ws.just_completed = True
                    if ws.workspace:
                        try:
                            chat_store.write_meta(
                                ws.workspace,
                                docs_count=docs_service.docs_count(ws.workspace),
                            )
                        except Exception:  # noqa: BLE001
                            pass
                else:
                    ws.phase = "idle"
            except asyncio.CancelledError:
                if generation == ws.generation:
                    ws.phase = "idle"
                    ws.status_message = ws.status_message or "Cancelled"
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
                if generation == ws.generation:
                    ws.turn_started_at = None


store = SessionStore()
