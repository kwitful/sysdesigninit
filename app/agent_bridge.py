"""ADK Runner bridge for web sessions (adapted from sys_des_in.runner)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

APP_NAME = "sysdesigninit"
USER_ID = "web-user"
_DESIGN_CONTEXT_CAP = 32_000


def load_dotenv() -> None:
    """Load ``sys_des_in/.env`` if present (does not override existing env)."""
    os.environ.setdefault("PYTHONUTF8", "1")
    env_path = Path(__file__).resolve().parent.parent / "sys_des_in" / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv as _load
    except ImportError:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
        return
    _load(env_path, override=False)


async def create_adk_session() -> Tuple[Runner, InMemorySessionService, str]:
    """Create Runner + session; import root_agent after dotenv is loaded."""
    load_dotenv()
    from sys_des_in.agents import root_agent

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    return runner, session_service, session.id


async def run_turn(
    runner: Runner,
    session_id: str,
    message: str,
) -> str:
    """Run one user→agent turn; return the final response text."""
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                parts_text = [
                    p.text for p in event.content.parts if getattr(p, "text", None)
                ]
                if parts_text:
                    final_text = "\n".join(parts_text)
            elif event.actions and getattr(event.actions, "escalate", False):
                final_text = (
                    f"Agent escalated: "
                    f"{getattr(event, 'error_message', None) or 'No message.'}"
                )
    return final_text or "(no final response)"


def _state_get(state: Any, key: str) -> Any:
    if state is None:
        return None
    if hasattr(state, "get"):
        return state.get(key)
    if isinstance(state, dict):
        return state.get(key)
    return None


async def read_state_keys(
    session_service: InMemorySessionService,
    session_id: str,
) -> Dict[str, Optional[str]]:
    """Best-effort read of workspace + design_context from ADK session state."""
    result: Dict[str, Optional[str]] = {"workspace": None, "design_context": None}
    try:
        session = await session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
    except Exception:  # noqa: BLE001
        return result
    if session is None:
        return result
    state = getattr(session, "state", None)
    workspace = _state_get(state, "workspace")
    if isinstance(workspace, str) and workspace.strip():
        result["workspace"] = workspace.strip()
    ctx = _state_get(state, "design_context")
    if isinstance(ctx, str) and ctx.strip():
        text = ctx.strip()
        if len(text) > _DESIGN_CONTEXT_CAP:
            text = text[:_DESIGN_CONTEXT_CAP]
        result["design_context"] = text
    return result


async def read_workspace_from_session(
    session_service: InMemorySessionService,
    session_id: str,
) -> Optional[str]:
    """Best-effort read of ``workspace`` from ADK session state."""
    keys = await read_state_keys(session_service, session_id)
    return keys.get("workspace")
