"""Workspace materialization for replay. NOT a security boundary.

`UnsafeLocalWorkspace` restores a snapshot into a fresh directory and runs
verification commands **directly on the host** — same user, same network,
same filesystem permissions. It isolates *state between forks* (each branch
gets its own tree), which is what paired replay needs; it does not isolate
*code from the machine*. Model-generated patches executed through it can do
anything your user account can.

Threat model and mitigations: docs/security.md. A rootless-container
backend with the same interface is the planned safe default; until it
lands, BYO-repo execution (`cdj run`) requires an explicit
`--unsafe-local-execution` acknowledgement.

The old name `LocalSandbox` is kept as a deprecated alias — "sandbox"
oversold what this does.
"""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from causal_data_juicer.store.blob import BlobStore


class UnsafeLocalWorkspace:
    def __init__(self, blob_store: BlobStore, scratch_root: Path):
        self.blobs = blob_store
        self.scratch_root = Path(scratch_root)
        self.scratch_root.mkdir(parents=True, exist_ok=True)

    def materialize(self, tree_digest: str) -> Path:
        dest = self.scratch_root / f"ws-{uuid.uuid4().hex[:10]}"
        return self.blobs.restore_tree(tree_digest, dest)

    def dispose(self, workspace: Path) -> None:
        ws = Path(workspace)
        root = Path(os.path.realpath(self.scratch_root))
        real = Path(os.path.realpath(ws))
        if root != real and root not in real.parents:
            raise ValueError(f"refusing to dispose outside scratch root: {workspace}")
        if ws.exists():
            shutil.rmtree(ws)


LocalSandbox = UnsafeLocalWorkspace  # deprecated alias
