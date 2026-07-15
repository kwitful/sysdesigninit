"""Safe multi-turn CLI for the system-design assistant.

Usage (from the project root that contains ``sys_des_in``)::

    python -m sys_des_in.runner
    python -m sys_des_in.runner "Design a URL shortener for a startup"

Design goals (fixes the broken clarify/input loop):

* Complete each agent turn fully before reading the next line of user input.
* Never call ``input()`` while events are still streaming.
* Flush stdout before prompting so typed characters are visible.
* Keep one stable session id across turns so clarification works.
* Print only the turn's final assistant text (not interleaved snippets that
  scramble the console).

Alternatively use ADK's built-in interactive CLI::

    adk run sys_des_in
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Windows + LiteLLM: force UTF-8 I/O (ADK LiteLLM docs).
os.environ.setdefault("PYTHONUTF8", "1")

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


APP_NAME = "sysdesigninit"
USER_ID = "cli-user"
_QUIT = frozenset({"quit", "exit", "q", ":q", "/quit", "/exit"})


def _load_dotenv() -> None:
    """Load ``sys_des_in/.env`` if present (does not override existing env)."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        # Minimal fallback so the CLI still works without python-dotenv.
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
        return
    load_dotenv(env_path, override=False)


def _prompt_user(label: str = "You") -> str | None:
    """Blocking stdin read AFTER the previous turn has fully finished.

    Returns None when the user wants to quit or stdin is closed.
    """
    sys.stdout.write(f"\n{label}> ")
    sys.stdout.flush()
    try:
        line = sys.stdin.readline()
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()
        return None
    if line == "":
        # EOF
        return None
    text = line.rstrip("\r\n")
    if text.strip().lower() in _QUIT:
        return None
    return text


async def _run_turn(
    runner: Runner,
    user_id: str,
    session_id: str,
    message: str,
) -> str:
    """Run one user→agent turn; return the final response text."""
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        # Only keep the concluding message for this turn. Printing mid-stream
        # text races with the next input() and causes empty/duplicated reads.
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


async def _session_loop(initial: str | None) -> None:
    # Import after dotenv so get_model() sees OPENROUTER_API_KEY / LLM_*.
    from .agents import root_agent

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    sys.stdout.write(
        "System-design assistant (multi-turn).\n"
        "Clarify with the coordinator; docs are written when it runs the "
        "pipeline.\n"
        "Type quit / exit / q to leave.\n"
    )
    sys.stdout.flush()

    pending = initial
    while True:
        if pending is None:
            pending = _prompt_user()
            if pending is None:
                break
        # Skip empty submits — do not send blank turns to the model.
        if not pending.strip():
            pending = None
            continue

        user_text = pending
        pending = None
        sys.stdout.write("\nAssistant is thinking…\n")
        sys.stdout.flush()
        try:
            reply = await _run_turn(runner, USER_ID, session.id, user_text)
        except Exception as exc:  # noqa: BLE001 — show and keep the REPL alive
            sys.stdout.write(f"\n[error] {exc}\n")
            sys.stdout.flush()
            continue

        sys.stdout.write(f"\nAssistant>\n{reply}\n")
        sys.stdout.flush()

    sys.stdout.write(
        "\nBye. Generated files (if any) are under "
        "sys_des_in/design_outputs/<workspace>/.\n"
    )
    sys.stdout.flush()


def main() -> None:
    _load_dotenv()
    initial = " ".join(sys.argv[1:]).strip() or None
    try:
        asyncio.run(_session_loop(initial))
    except KeyboardInterrupt:
        sys.stdout.write("\nInterrupted.\n")
        sys.stdout.flush()
        sys.exit(130)


if __name__ == "__main__":
    main()
