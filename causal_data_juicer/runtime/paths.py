"""The single choke point for turning agent-supplied paths into real paths.

Every file operation that takes a path from outside the engine — agent tool
calls, recorded actions (which may come from imported, untrusted traces),
seal restores — must resolve it here. There is deliberately no second,
weaker code path.

Rules enforced (all four raise ``WorkspaceEscapeError``):
- absolute paths are rejected;
- any ``..`` component is rejected, before any filesystem access;
- an *intermediate* component that is a symlink is rejected outright
  (even one pointing inside the workspace — link-swap races are not worth
  reasoning about);
- a *final* symlink is rejected by default; with ``allow_symlink=True`` it
  is followed only if its real target stays inside the workspace.

A final ``realpath`` containment check backstops the walk.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath


class WorkspaceEscapeError(ValueError):
    """A user-supplied path tried to leave its workspace."""


def resolve_workspace_path(
    workspace: Path,
    user_path: str,
    *,
    must_exist: bool = False,
    allow_symlink: bool = False,
) -> Path:
    ws = Path(workspace)
    ws_real = Path(os.path.realpath(ws))
    if not ws_real.is_dir():
        raise WorkspaceEscapeError(f"workspace does not exist: {workspace}")

    raw = str(user_path)
    if PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute():
        raise WorkspaceEscapeError(f"absolute paths are not allowed: {raw}")

    parts = [p for p in PurePosixPath(raw).parts if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise WorkspaceEscapeError(f"path escapes workspace: {raw}")

    cur = ws_real
    for i, part in enumerate(parts):
        cur = cur / part
        is_final = i == len(parts) - 1
        if cur.is_symlink():
            if not is_final:
                raise WorkspaceEscapeError(
                    f"intermediate symlink in path: {raw} (at {part})")
            if not allow_symlink:
                raise WorkspaceEscapeError(f"path is a symlink: {raw}")
            real = Path(os.path.realpath(cur))
            if ws_real != real and ws_real not in real.parents:
                raise WorkspaceEscapeError(
                    f"symlink resolves outside workspace: {raw}")

    real_final = Path(os.path.realpath(cur))
    if ws_real != real_final and ws_real not in real_final.parents:
        raise WorkspaceEscapeError(f"path escapes workspace: {raw}")

    if must_exist and not cur.exists():
        raise FileNotFoundError(raw)
    return cur
