"""Safe list/read/zip over design_outputs."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from sys_des_in.tools.file_tools import ALLOWED_DESIGN_FILES, PIPELINE_FILE_ORDER

from .config import PIPELINE_LABELS
from .security import (
    SecurityError,
    outputs_root,
    resolve_doc_path,
    resolve_workspace_dir,
    validate_filename,
    validate_workspace_name,
)


@dataclass(frozen=True)
class FileEntry:
    name: str
    ready: bool


@dataclass(frozen=True)
class PipelineStep:
    id: str
    label: str
    status: str  # pending | ready


@dataclass(frozen=True)
class WorkspaceInfo:
    name: str
    problem: Optional[str]
    mtime: Optional[float] = None
    docs_count: int = 0


def docs_total() -> int:
    return len(PIPELINE_FILE_ORDER)


def list_files(workspace: str) -> List[FileEntry]:
    """Return allowlisted files with readiness for a workspace."""
    ws_dir = resolve_workspace_dir(workspace)
    present: set[str] = set()
    if ws_dir.is_dir():
        for name in ALLOWED_DESIGN_FILES:
            if (ws_dir / name).is_file():
                present.add(name)
    return [FileEntry(name=name, ready=name in present) for name in PIPELINE_FILE_ORDER]


def ready_filenames(workspace: Optional[str]) -> set[str]:
    if not workspace:
        return set()
    try:
        return {e.name for e in list_files(workspace) if e.ready}
    except SecurityError:
        return set()


def pipeline_status(workspace: Optional[str]) -> List[PipelineStep]:
    present = ready_filenames(workspace)
    return [
        PipelineStep(
            id=name,
            label=PIPELINE_LABELS.get(name, name),
            status="ready" if name in present else "pending",
        )
        for name in PIPELINE_FILE_ORDER
    ]


def docs_count(workspace: Optional[str]) -> int:
    return len(ready_filenames(workspace))


def all_docs_ready(workspace: Optional[str]) -> bool:
    if not workspace:
        return False
    present = ready_filenames(workspace)
    return len(present) == len(PIPELINE_FILE_ORDER)


def read_markdown(workspace: str, filename: str) -> str:
    path = resolve_doc_path(workspace, filename)
    if not path.is_file():
        raise FileNotFoundError(f"File '{filename}' not found.")
    return path.read_text(encoding="utf-8")


def list_workspaces(*, q: Optional[str] = None) -> List[WorkspaceInfo]:
    root = outputs_root()
    if not root.is_dir():
        return []
    query = (q or "").strip().lower()
    results: List[WorkspaceInfo] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        try:
            name = validate_workspace_name(child.name)
            resolve_workspace_dir(name)
        except SecurityError:
            continue
        problem: Optional[str] = None
        marker = child / ".problem.txt"
        if marker.is_file():
            try:
                problem = marker.read_text(encoding="utf-8").strip() or None
            except OSError:
                problem = None
        if query:
            hay = f"{name} {problem or ''}".lower()
            if query not in hay:
                continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            mtime = None
        count = docs_count(name)
        results.append(
            WorkspaceInfo(name=name, problem=problem, mtime=mtime, docs_count=count)
        )
    return results


def workspace_exists(name: str) -> bool:
    try:
        safe = validate_workspace_name(name)
        path = resolve_workspace_dir(safe)
    except SecurityError:
        return False
    return path.is_dir()


def read_problem(workspace: Optional[str]) -> Optional[str]:
    """Read .problem.txt for a workspace (path-safe); None if missing."""
    if not workspace:
        return None
    try:
        ws_dir = resolve_workspace_dir(workspace)
    except SecurityError:
        return None
    marker = ws_dir / ".problem.txt"
    if not marker.is_file():
        return None
    try:
        text = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def build_workspace_zip(workspace: str) -> bytes:
    """Zip allowlisted files only; arcnames are bare filenames."""
    ws_dir = resolve_workspace_dir(workspace)
    if not ws_dir.is_dir():
        raise FileNotFoundError("Workspace not found.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in PIPELINE_FILE_ORDER:
            validate_filename(name)
            path = resolve_doc_path(workspace, name)
            if path.is_file():
                zf.write(path, arcname=name)
    return buf.getvalue()
