"""Persist chat transcripts as chat.json under design workspaces."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import MAX_MESSAGE_LENGTH
from .security import resolve_workspace_dir, validate_workspace_name

CHAT_FILENAME = "chat.json"
META_FILENAME = "meta.json"
MAX_MESSAGES = 200
_WEB_SIDECARS = frozenset({CHAT_FILENAME, META_FILENAME})


def resolve_sidecar_path(workspace: str, filename: str) -> Path:
    """Resolve a web-managed sidecar file under the workspace (path-safe)."""
    if filename not in _WEB_SIDECARS:
        raise ValueError("Sidecar filename is not allowed.")
    safe = validate_workspace_name(workspace)
    ws_dir = resolve_workspace_dir(safe)
    path = (ws_dir / filename).resolve()
    try:
        path.relative_to(ws_dir)
    except ValueError as exc:
        raise ValueError("Sidecar path escapes workspace.") from exc
    if path.name != filename:
        raise ValueError("Invalid sidecar path.")
    return path


def _normalize_message(role: str, text: str, ts: Optional[float] = None) -> Dict[str, Any]:
    if role not in ("user", "assistant"):
        raise ValueError("Invalid message role.")
    cleaned = (text or "").replace("\x00", "").strip()
    if not cleaned:
        raise ValueError("Empty message.")
    if len(cleaned) > MAX_MESSAGE_LENGTH:
        cleaned = cleaned[:MAX_MESSAGE_LENGTH]
    return {"role": role, "text": cleaned, "ts": ts if ts is not None else time.time()}


def load_chat(workspace: str) -> List[Dict[str, Any]]:
    """Load and validate chat.json; return [] if missing or invalid."""
    try:
        path = resolve_sidecar_path(workspace, CHAT_FILENAME)
    except (ValueError, Exception):
        return []
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, dict) or raw.get("version") != 1:
        return []
    messages = raw.get("messages")
    if not isinstance(messages, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in messages[-MAX_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                _normalize_message(
                    str(item.get("role", "")),
                    str(item.get("text", "")),
                    float(item["ts"]) if item.get("ts") is not None else None,
                )
            )
        except (ValueError, TypeError):
            continue
    return out


def save_chat(workspace: str, messages: List[Dict[str, Any]]) -> None:
    """Atomically write chat.json."""
    path = resolve_sidecar_path(workspace, CHAT_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized: List[Dict[str, Any]] = []
    for item in messages[-MAX_MESSAGES:]:
        try:
            normalized.append(
                _normalize_message(
                    str(item.get("role", "")),
                    str(item.get("text", "")),
                    float(item["ts"]) if item.get("ts") is not None else None,
                )
            )
        except (ValueError, TypeError):
            continue
    payload = {"version": 1, "messages": normalized}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def append_turn(
    workspace: str,
    *,
    user_text: str,
    assistant_text: str,
) -> List[Dict[str, Any]]:
    """Append a user+assistant turn and return the full message list."""
    messages = load_chat(workspace)
    now = time.time()
    messages.append(_normalize_message("user", user_text, now))
    messages.append(_normalize_message("assistant", assistant_text, now + 0.001))
    save_chat(workspace, messages)
    return messages


def write_meta(workspace: str, *, docs_count: int) -> None:
    """Write meta.json on pipeline completion."""
    path = resolve_sidecar_path(workspace, META_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "completed_at": time.time(),
        "docs_count": docs_count,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
