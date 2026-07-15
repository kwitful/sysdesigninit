"""Session-state tools for the coordinator → pipeline handoff.

ADK injects ``ToolContext`` when it is declared as the last parameter of a
tool function. Writing ``design_context`` and ``workspace`` into
``tool_context.state`` is the reliable way to share the brief with the
SequentialAgent pipeline when it is invoked via ``AgentTool``.
"""

from __future__ import annotations

from typing import Any, Dict

from google.adk.tools.tool_context import ToolContext

from .file_tools import init_design_workspace as _init_workspace_disk


def init_design_workspace(problem: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Create a design workspace on disk and remember its name in session state.

    Call this once when you are ready to generate documents (after clarifying
    the problem). The returned ``workspace`` value (also stored in state as
    ``workspace``) must be used by later ``write_design_doc`` calls.

    Args:
        problem: Short human-readable problem name, e.g. "URL shortener for a
            startup".
        tool_context: Injected by ADK; used to persist ``workspace`` in session
            state for the document pipeline.

    Returns:
        Dict with ``status``, ``workspace``, and ``path``.
    """
    result = _init_workspace_disk(problem)
    if result.get("status") == "success":
        tool_context.state["workspace"] = result["workspace"]
    return result


def save_design_context(content: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Save the structured design brief into session state before running the pipeline.

    The content MUST be the full markdown brief with sections: Problem, Scale,
    Quality Targets, Maturity, Must-have Features, Out of Scope, and Reasoning.
    Specialist agents read this via ``{design_context}``.

    Args:
        content: Full markdown design-context brief.
        tool_context: Injected by ADK.

    Returns:
        Dict with ``status`` and ``chars`` written.
    """
    text = (content or "").strip()
    if not text:
        return {
            "status": "error",
            "error_message": "content must be a non-empty design-context brief.",
        }
    tool_context.state["design_context"] = text
    return {"status": "success", "chars": len(text)}
