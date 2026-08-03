"""Content-addressed blob store for workspace snapshots.

Snapshot identity (schema v2) covers, per node: relative path, node type
(file/symlink), permission mode, content hash or symlink target, and size.
The v1 digest covered only path + content bytes, so `chmod +x` and
symlink-vs-copy were invisible to "byte-identical" claims, and symlinks
were silently flattened into regular files on store — all fixed here.

Version coexistence: v2 digests carry a ``v2-`` prefix. Trees stored under
v1 digests remain restorable (legacy path, no verification), so old runs
and committed replay packs keep replaying; `cdj migrate-run` re-digests
stored trees and rewrites run metadata to v2.

Symlinks are never followed — neither into the store nor out of it. Links
whose targets lie outside the tree are recorded as links (target string),
not their contents.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

IGNORED_DIRS = {"__pycache__", ".pytest_cache", ".git", ".venv"}

SCHEMA_PREFIX = "v2-"


def _iter_nodes(root: Path):
    """Yield (path, rel, kind) for files and symlinks, links never followed."""
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if p.is_symlink():
            yield p, rel, "symlink"
        elif p.is_file():
            yield p, rel, "file"


def _node_record(p: Path, rel: Path, kind: str) -> dict:
    st = p.lstat()
    rec = {
        "relative_path": str(rel),
        "node_type": kind,
        "mode": oct(st.st_mode & 0o7777),
        "size": st.st_size,
    }
    if kind == "symlink":
        rec["symlink_target"] = os.readlink(p)
    else:
        rec["content_hash"] = hashlib.sha256(p.read_bytes()).hexdigest()
    return rec


def tree_records(root: Path) -> list[dict]:
    return [_node_record(p, rel, kind) for p, rel, kind in _iter_nodes(root)]


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for rec in tree_records(root):
        h.update(json.dumps(rec, sort_keys=True).encode())
        h.update(b"\0")
    return SCHEMA_PREFIX + h.hexdigest()[:16]


def tree_digest_v1(root: Path) -> str:
    """Legacy digest (path + content only). Kept for reading old runs."""
    h = hashlib.sha256()
    for p, rel, kind in _iter_nodes(root):
        if kind != "file":
            continue
        h.update(str(rel).encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:16]


def digests_match(recorded: str, root: Path) -> bool:
    """Compare a live tree against a recorded digest, schema-aware: old runs
    recorded v1 digests and must keep matching after the v2 switch."""
    if recorded.startswith(SCHEMA_PREFIX):
        return tree_digest(root) == recorded
    return tree_digest_v1(root) == recorded


def _copy_tree_nodes(src_root: Path, dest_root: Path) -> None:
    for p, rel, kind in _iter_nodes(src_root):
        target = dest_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if kind == "symlink":
            os.symlink(os.readlink(p), target)
        else:
            shutil.copy2(p, target)  # copy2 preserves mode


class BlobStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _meta_path(self, digest: str) -> Path:
        return self.root / f"{digest}.meta.json"

    def put_tree(self, workspace: Path) -> str:
        records = tree_records(workspace)
        h = hashlib.sha256()
        for rec in records:
            h.update(json.dumps(rec, sort_keys=True).encode())
            h.update(b"\0")
        digest = SCHEMA_PREFIX + h.hexdigest()[:16]
        dest = self.root / digest
        if not dest.exists():
            tmp = self.root / f".tmp-{uuid.uuid4().hex}"   # unique: no concurrent collisions
            tmp.mkdir(parents=True)
            _copy_tree_nodes(workspace, tmp)
            meta_tmp = self.root / f".tmp-meta-{uuid.uuid4().hex}"
            with open(meta_tmp, "w") as f:
                f.write(json.dumps({"schema": 2, "nodes": records}))
                f.flush()
                os.fsync(f.fileno())
            try:
                os.replace(tmp, dest)                      # atomic commit
                os.replace(meta_tmp, self._meta_path(digest))
            except OSError:
                # lost the race to a concurrent writer of the same digest
                shutil.rmtree(tmp, ignore_errors=True)
                meta_tmp.unlink(missing_ok=True)
        return digest

    def restore_tree(self, digest: str, dest: Path) -> Path:
        src = self.root / digest
        if not src.exists():
            raise KeyError(f"unknown tree digest {digest}")
        dest = Path(dest)
        if dest.exists():
            raise FileExistsError(
                f"restore destination already exists: {dest} — "
                f"materialize into fresh directories only")
        if digest.startswith(SCHEMA_PREFIX):
            dest.mkdir(parents=True)
            _copy_tree_nodes(src, dest)
            got = tree_digest(dest)
            if got != digest:
                raise RuntimeError(
                    f"post-restore digest mismatch: wanted {digest}, got {got}")
        else:                                              # legacy v1 blob
            shutil.copytree(src, dest, symlinks=True)
        return dest

    def has(self, digest: str) -> bool:
        return (self.root / digest).exists()
