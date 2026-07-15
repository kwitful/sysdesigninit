"""Command-line runner for the system-design pipeline.

Usage:
    python -m sys_des_in.runner "Design a URL shortener for a startup"

or, from inside the ``sys_des_in`` directory:
    python runner.py "Design a URL shortener for a startup"

The runner creates an in-memory session, sends the user's problem as the first
message, and streams the agent events to stdout. When the pipeline finishes
the written markdown files live under ``sys_des_in/design_outputs/<workspace>/``.
"""

from __future__ import annotations

import asyncio
import sys

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .agents import root_agent

APP_NAME = "sysdesigninit"
USER_ID = "cli-user"


async def _run(problem: str) -> None:
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    content = types.Content(
        role="user", parts=[types.Part(text=problem)]
    )

    print(f"\n>>> Designing: {problem}\n")
    final_text = "(no final response)"
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=content,
    ):
        author = getattr(event, "author", "?")
        if event.is_final_response():
            if event.content and event.content.parts:
                final_text = event.content.parts[0].text
            print(f"\n<<< [{author}] {final_text}")
            break
        # Surface intermediate progress so the user sees the pipeline moving.
        if event.content and event.content.parts:
            snippet = event.content.parts[0].text
            if snippet:
                snippet = snippet.replace("\n", " ")
                print(f"  [{author}] {snippet[:200]}")

    print(
        "\nDone. Check design_outputs/ for the generated markdown files.\n"
    )


def main() -> None:
    if len(sys.argv) < 2:
        print(
            'Usage: python -m sys_des_in.runner "Design a URL shortener for a '
            'startup"'
        )
        sys.exit(1)
    problem = " ".join(sys.argv[1:])
    asyncio.run(_run(problem))


if __name__ == "__main__":
    main()
