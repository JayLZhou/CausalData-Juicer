"""M3 storage-bench: replay-cost vs storage trade-off of checkpoint
placement, measured on a real run's fork points.

For every validated unit's fork point, fork the workspace under each
placement policy (sparse checkpoints force prefix re-execution) and
measure wall time + steps re-executed; storage is the byte footprint of
each policy's kept checkpoints.  The A6 number is the fork-cost speedup
of checkpoint-everywhere vs the from-scratch baseline, extrapolated over
the branches an acquisition run actually pays for.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.replay.sandbox import UnsafeLocalWorkspace
from causal_data_juicer.run_store import RunStore
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import PytestVerifier
from causal_data_juicer.sdk.schemas import EvidenceTier
from causal_data_juicer.store.blob import digests_match
from causal_data_juicer.store.dag import dag_stats, select_checkpoints, storage_bytes


def storage_bench(run_dir: Path, policies: list[str], repeats: int = 3) -> dict:
    store = RunStore(run_dir)
    episodes = {ep.id: ep for ep in store.load_episodes()}
    snapshots = store.load_snapshots()
    units = [u for u in store.load_units() if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED]
    replayer = Replayer(
        default_registry(),
        UnsafeLocalWorkspace(store.blobs, Path(run_dir) / "scratch-m3"),
        PytestVerifier(),
    )
    fork_points = [(episodes[u.episode_id], u.effective_intervention().target_step) for u in units]

    blob_root = store.blobs.root
    rows: list[dict[str, Any]] = []
    for policy in policies:
        kept = select_checkpoints(snapshots, policy)
        total_s, total_prefix, forks = 0.0, 0, 0
        equivalent = True
        for ep, step in fork_points:
            for _ in range(repeats):
                t0 = time.monotonic()
                ws, prefix = replayer.fork_at(ep, kept, step)
                total_s += time.monotonic() - t0
                total_prefix += prefix
                forks += 1
                # state equivalence: sparse fork must reconstruct the exact
                # tree the dense checkpoint recorded
                if policy != "every":
                    dense = next(
                        s for s in snapshots if s.episode_id == ep.id and s.step_index == step
                    )
                    equivalent &= digests_match(dense.tree_digest, ws)
                replayer.sandbox.dispose(ws)
        rows.append(
            {
                "policy": policy,
                "checkpoints_kept": len(kept),
                "storage_bytes": storage_bytes(kept, blob_root),
                "avg_fork_s": round(total_s / max(1, forks), 4),
                "avg_prefix_steps": round(total_prefix / max(1, forks), 2),
                "state_equivalent": equivalent,
            }
        )

    base = next(r for r in rows if r["policy"] == "first")
    for r in rows:
        r["fork_speedup_vs_first"] = round(base["avg_fork_s"] / max(1e-9, r["avg_fork_s"]), 2)
        r["storage_x_vs_first"] = round(r["storage_bytes"] / max(1, base["storage_bytes"]), 2)
    return {
        "run": str(run_dir),
        "fork_points": len(fork_points),
        "repeats": repeats,
        "dag": dag_stats(list(episodes.values()), snapshots, blob_root),
        "policies": rows,
    }


def print_bench(report: dict) -> None:
    d = report["dag"]
    print(
        f"trace DAG: {d['snapshot_references']} snapshot refs -> {d['unique_trees']} unique "
        f"trees (sharing {d['sharing_ratio']}x, bytes saved {d['bytes_saved_pct']}%)"
    )
    print(
        f"{'policy':<12}{'ckpts':<7}{'storage':<10}{'fork_s':<9}{'prefix':<8}"
        f"{'speedup':<9}{'equiv'}"
    )
    for r in report["policies"]:
        print(
            f"{r['policy']:<12}{r['checkpoints_kept']:<7}"
            f"{r['storage_bytes'] / 1e6:<10.2f}{r['avg_fork_s']:<9.4f}"
            f"{r['avg_prefix_steps']:<8}{r['fork_speedup_vs_first']:<9}"
            f"{'OK' if r['state_equivalent'] else 'MISMATCH'}"
        )
