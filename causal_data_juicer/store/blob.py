"""Content-addressed blob store for workspace snapshots.

A snapshot is a full copy of the workspace tree keyed by a deterministic
tree digest.  Identical trees are stored once (shared-prefix reuse across
episodes and replays comes for free at M1 scale; the trace DAG proper is
M3 territory).
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

IGNORED_DIRS = {"__pycache__", ".pytest_cache", ".git", ".venv"}


def _iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if any(part in IGNORED_DIRS for part in p.relative_to(root).parts):
            continue
        if p.is_file():
            yield p


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for p in _iter_files(root):
        h.update(str(p.relative_to(root)).encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:16]


class BlobStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_tree(self, workspace: Path) -> str:
        digest = tree_digest(workspace)
        dest = self.root / digest
        if not dest.exists():
            tmp = self.root / f".tmp-{digest}"
            if tmp.exists():
                shutil.rmtree(tmp)
            tmp.mkdir(parents=True)
            for p in _iter_files(workspace):
                rel = p.relative_to(workspace)
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, tmp / rel)
            tmp.rename(dest)
        return digest

    def restore_tree(self, digest: str, dest: Path) -> Path:
        src = self.root / digest
        if not src.exists():
            raise KeyError(f"unknown tree digest {digest}")
        dest = Path(dest)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return dest

    def has(self, digest: str) -> bool:
        return (self.root / digest).exists()
