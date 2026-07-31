"""Shared-prefix trace DAG statistics and checkpoint placement (M3).

The blob store is content-addressed, so the trace "DAG" is implicit:
every snapshot references a tree digest, identical states collapse into
one physical blob (repro forks, shared prefixes, identical task setups).
``dag_stats`` quantifies that sharing; ``select_checkpoints`` implements
placement policies whose replay-cost/storage trade-off ``storage-bench``
measures on real runs.
"""
from __future__ import annotations

import os
from pathlib import Path

from causal_data_juicer.sdk.schemas import Episode, Snapshot


def _blob_bytes(blob_root: Path, digest: str) -> int:
    root = Path(blob_root) / digest
    if not root.exists():
        return 0
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())


def dag_stats(episodes: list[Episode], snapshots: list[Snapshot], blob_root: Path) -> dict:
    references = [s.tree_digest for s in snapshots] + \
        [ep.final_tree_digest for ep in episodes if ep.final_tree_digest]
    unique = sorted(set(references))
    sizes = {d: _blob_bytes(blob_root, d) for d in unique}
    bytes_logical = sum(sizes[d] for d in references)
    bytes_physical = sum(sizes.values())
    return {
        "snapshot_references": len(references),
        "unique_trees": len(unique),
        "sharing_ratio": round(len(references) / max(1, len(unique)), 2),
        "bytes_logical": bytes_logical,
        "bytes_physical": bytes_physical,
        "bytes_saved_pct": round(100 * (1 - bytes_physical / max(1, bytes_logical)), 1),
    }


def select_checkpoints(snapshots: list[Snapshot], policy: str) -> list[Snapshot]:
    """Placement policies over an episode's step-boundary snapshots.

    every      keep all (M1 default: fork anywhere at restore cost)
    first      keep only step 0 (the from-scratch baseline: forking at
               step k re-executes the whole recorded prefix)
    every_k:N  keep steps 0, N, 2N, ... (the middle of the trade-off)
    """
    if policy == "every":
        return list(snapshots)
    by_episode: dict[str, list[Snapshot]] = {}
    for s in sorted(snapshots, key=lambda s: s.step_index):
        by_episode.setdefault(s.episode_id, []).append(s)
    kept: list[Snapshot] = []
    if policy == "first":
        for snaps in by_episode.values():
            kept.append(snaps[0])
        return kept
    if policy.startswith("every_k:"):
        k = int(policy.split(":", 1)[1])
        for snaps in by_episode.values():
            kept.extend(s for s in snaps if s.step_index % k == 0)
        return kept
    raise ValueError(f"unknown checkpoint policy: {policy}")


def storage_bytes(snapshots: list[Snapshot], blob_root: Path) -> int:
    return sum(_blob_bytes(blob_root, d) for d in {s.tree_digest for s in snapshots})
