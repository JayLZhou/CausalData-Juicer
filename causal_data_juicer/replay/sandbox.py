"""Local sandbox: isolated workspace directories restored from snapshots.

Forking only happens at step boundaries; a sandbox is just a fresh
directory materialized from a content-addressed tree.  A Docker-backed
sandbox with the same interface is planned for M1.5 (workload adapter).
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from causal_data_juicer.store.blob import BlobStore


class LocalSandbox:
    def __init__(self, blob_store: BlobStore, scratch_root: Path):
        self.blobs = blob_store
        self.scratch_root = Path(scratch_root)
        self.scratch_root.mkdir(parents=True, exist_ok=True)

    def materialize(self, tree_digest: str) -> Path:
        dest = self.scratch_root / f"ws-{uuid.uuid4().hex[:10]}"
        return self.blobs.restore_tree(tree_digest, dest)

    def dispose(self, workspace: Path) -> None:
        if Path(workspace).exists():
            shutil.rmtree(workspace)
