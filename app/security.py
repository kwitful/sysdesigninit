"""Path and input hardening for the web API."""

from __future__ import annotations

import re
from pathlib import Path

from sys_des_in.tools.file_tools import (
    ALLOWED_DESIGN_FILES,
    get_outputs_root,
    is_allowed_filename,
    sanitize_workspace,
)

_UNSAFE_WORKSPACE = re.compile(r"[/\\]|\.\.")


class SecurityError(ValueError):
    """Raised when a path or name fails validation."""


def validate_message_text(text: str, *, max_length: int) -> str:
    """Normalize and validate a user chat message."""
    if text is None:
        raise SecurityError("Message text is required.")
    # Strip NULs; normalize newlines.
    cleaned = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.strip()
    if not cleaned:
        raise SecurityError("Message text must not be empty.")
    if len(cleaned) > max_length:
        raise SecurityError(f"Message exceeds maximum length of {max_length} characters.")
    return cleaned


def validate_workspace_name(name: str) -> str:
    """Return a sanitized workspace name or raise SecurityError."""
    if not name or not str(name).strip():
        raise SecurityError("Workspace name is required.")
    raw = str(name).strip()
    if _UNSAFE_WORKSPACE.search(raw) or raw in (".", ".."):
        raise SecurityError("Invalid workspace name.")
    safe = sanitize_workspace(raw)
    # Reject if sanitization changed meaning in a suspicious way (e.g. path bits).
    if not safe or safe != sanitize_workspace(safe):
        raise SecurityError("Invalid workspace name.")
    return safe


def validate_filename(filename: str) -> str:
    """Ensure filename is on the design-doc allowlist."""
    if not filename or not is_allowed_filename(filename):
        raise SecurityError("Filename is not allowed.")
    return filename


def outputs_root() -> Path:
    return Path(get_outputs_root()).resolve()


def resolve_workspace_dir(workspace: str) -> Path:
    """Resolve workspace directory under outputs root; raise if it escapes."""
    safe = validate_workspace_name(workspace)
    root = outputs_root()
    path = (root / safe).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SecurityError("Workspace path escapes outputs root.") from exc
    return path


def resolve_doc_path(workspace: str, filename: str) -> Path:
    """Resolve an allowlisted doc path under the workspace; raise if unsafe."""
    fname = validate_filename(filename)
    ws_dir = resolve_workspace_dir(workspace)
    path = (ws_dir / fname).resolve()
    try:
        path.relative_to(ws_dir)
    except ValueError as exc:
        raise SecurityError("Document path escapes workspace.") from exc
    if path.name not in ALLOWED_DESIGN_FILES:
        raise SecurityError("Filename is not allowed.")
    return path


def sanitize_error_message(exc: BaseException) -> str:
    """Return a client-safe error string (no secrets / long traces)."""
    msg = str(exc) or exc.__class__.__name__
    # Redact common secret patterns.
    msg = re.sub(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+", r"\1=[redacted]", msg)
    msg = re.sub(r"sk-[a-zA-Z0-9_-]+", "[redacted]", msg)
    msg = re.sub(r"AIza[0-9A-Za-z_-]+", "[redacted]", msg)
    if len(msg) > 400:
        msg = msg[:397] + "..."
    return msg
