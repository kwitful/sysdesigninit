"""Filesystem tools for the system-design assistant.

Each design run gets its own workspace directory under ``design_outputs/`` so
that multiple problems can be designed without overwriting each other.

The agents call these tools to persist the markdown documents they produce.
A docstring is provided for every tool because ADK relies on it to explain the
tool to the underlying LLM.
"""

from __future__ import annotations

import os
import re
from typing import Dict

# Root directory where all design workspaces live. Resolved relative to this
# file so it works no matter where the agent is launched from.
_OUTPUTS_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "design_outputs")
)

# Whitelist of filenames the pipeline is allowed to write. This prevents an
# agent from scribbling arbitrary files on disk.
_ALLOWED_FILES = {
    "00-problem-brief.md",
    "00-index.md",
    "00-review.md",
    "01-requirements.md",
    "02-architecture.md",
    "03-api.md",
    "04-data-model.md",
    "05-component-design.md",
    "06-resilience.md",
    "07-security-ops.md",
    "08-decisions-log.md",
    "09-capacity-estimates.md",
}


def _sanitize_workspace(name: str) -> str:
    """Turn a free-form problem name into a safe directory name."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    if not name:
        name = "design"
    return name[:80]


def _workspace_path(workspace: str) -> str:
    workspace = _sanitize_workspace(workspace)
    return os.path.join(_OUTPUTS_ROOT, workspace)


def init_design_workspace(problem: str) -> Dict[str, str]:
    """Create a fresh workspace directory for a system-design run.

    Use this once at the start of a design to get a clean folder. Any previous
    documents with the same problem name are left in place; later writes
    overwrite individual files.

    Args:
        problem: A short human-readable description of the system to design,
            e.g. "URL shortener for a startup" or "Netflix-like video platform".

    Returns:
        A dict with:
            - ``status``: "success"
            - ``workspace``: the sanitized workspace name used for later calls
            - ``path``: absolute path to the workspace directory on disk
    """
    workspace = _sanitize_workspace(problem)
    path = _workspace_path(workspace)
    os.makedirs(path, exist_ok=True)
    # Drop a small marker file so the folder is self-describing.
    marker = os.path.join(path, ".problem.txt")
    if not os.path.exists(marker):
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(problem + "\n")
    return {"status": "success", "workspace": workspace, "path": path}


def write_design_doc(workspace: str, filename: str, content: str) -> Dict[str, str]:
    """Write a single markdown design document to the workspace.

    Only a fixed set of filenames is allowed (design sections, brief, decisions,
    capacity, index, and review). The content is written verbatim and a timestamped header is not
    added by the tool — the agent controls the full document body so it can
    include its own Reasoning footer.

    Args:
        workspace: The workspace name returned by ``init_design_workspace``.
        filename: One of the allowed filenames, e.g. "01-requirements.md".
        content: The full markdown text to write, including any Reasoning
            section.

    Returns:
        A dict with ``status`` ("success" or "error"), ``filename``, ``path``,
        and ``bytes_written``. On error, ``error_message`` is set instead.
    """
    if filename not in _ALLOWED_FILES:
        return {
            "status": "error",
            "error_message": (
                f"Filename '{filename}' is not allowed. "
                f"Allowed files: {sorted(_ALLOWED_FILES)}"
            ),
        }

    path = _workspace_path(workspace)
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, filename)
    data = content.encode("utf-8")
    with open(file_path, "wb") as fh:
        fh.write(data)
    return {
        "status": "success",
        "filename": filename,
        "path": file_path,
        "bytes_written": len(data),
    }


def read_design_doc(workspace: str, filename: str, limit: int = 5000) -> Dict[str, object]:
    """Read a previously written design document from the workspace.

    Useful when a later agent needs to ground itself in the exact text an
    earlier agent produced (in addition to the shared session state).

    Args:
        workspace: The workspace name returned by ``init_design_workspace``.
        filename: One of the allowed filenames.
        limit: Maximum number of lines to return, to avoid blowing up the
            model context. Defaults to 5000.

    Returns:
        A dict with ``status``, ``filename``, and ``content`` (the file text).
        If the file does not exist, ``status`` is "error" with
        ``error_message``.
    """
    if filename not in _ALLOWED_FILES:
        return {
            "status": "error",
            "error_message": f"Filename '{filename}' is not allowed.",
        }
    file_path = os.path.join(_workspace_path(workspace), filename)
    if not os.path.exists(file_path):
        return {
            "status": "error",
            "error_message": f"File '{filename}' not found in workspace '{workspace}'.",
        }
    with open(file_path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    text = "".join(lines[:limit])
    return {
        "status": "success",
        "filename": filename,
        "content": text,
        "lines_returned": min(len(lines), limit),
        "total_lines": len(lines),
    }


def list_design_docs(workspace: str) -> Dict[str, object]:
    """List the design documents that currently exist in a workspace.

    Args:
        workspace: The workspace name returned by ``init_design_workspace``.

    Returns:
        A dict with ``status`` and ``files`` (a list of filenames present).
    """
    path = _workspace_path(workspace)
    if not os.path.isdir(path):
        return {"status": "success", "files": []}
    files = sorted(
        f for f in os.listdir(path)
        if f in _ALLOWED_FILES and os.path.isfile(os.path.join(path, f))
    )
    return {"status": "success", "files": files, "path": path}
