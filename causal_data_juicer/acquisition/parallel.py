"""Parallel candidate validation (the last P1 engineering item).

Paired replays are embarrassingly parallel across candidates — each
validation forks its own sandbox — so a process pool multiplies replay
throughput. Workers rebuild their engine from paths (everything that
crosses the boundary is pydantic-serializable); the control-branch
memoization becomes per-worker, trading a few duplicate control replays
for wall-clock. Determinism is untouched: same replays, same digests,
just more of them at once.
"""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from causal_data_juicer.sdk.schemas import CausalUnit, Episode, Intervention, Snapshot

_WORKER = {}


def _init_worker(blobs_root: str, scratch_root: str, verify_argv: list[str] | None):
    from causal_data_juicer.replay.replayer import Replayer
    from causal_data_juicer.replay.sandbox import UnsafeLocalWorkspace
    from causal_data_juicer.runtime.tools import default_registry
    from causal_data_juicer.runtime.verifier import CommandVerifier, PytestVerifier
    from causal_data_juicer.store.blob import BlobStore

    verifier = CommandVerifier(verify_argv) if verify_argv else PytestVerifier()
    scratch = Path(scratch_root) / f"w{os.getpid()}"
    _WORKER["replayer"] = Replayer(default_registry(),
                                   UnsafeLocalWorkspace(BlobStore(Path(blobs_root)), scratch),
                                   verifier)
    _WORKER["control_cache"] = {}


def _validate_one(payload: tuple[str, str, str, int]) -> str:
    episode_json, snapshots_json, intervention_json, n_repro = payload
    import json as _json
    episode = Episode.model_validate_json(episode_json)
    snapshots = [Snapshot.model_validate_json(s) for s in _json.loads(snapshots_json)]
    intervention = Intervention.model_validate_json(intervention_json)
    unit = _WORKER["replayer"].paired_replay(
        episode, snapshots, intervention, n_repro=n_repro,
        control_cache=_WORKER["control_cache"], early_stop_repro=True)
    return unit.model_dump_json()


def validate_parallel(
    candidates: list[tuple[Episode, Intervention]],
    snapshots: list[Snapshot],
    blobs_root: Path,
    scratch_root: Path,
    n_repro: int = 3,
    workers: int = 4,
    verify_argv: list[str] | None = None,
) -> list[CausalUnit]:
    """Validate candidates across a process pool; order preserved."""
    import json as _json
    snap_by_ep: dict[str, list[Snapshot]] = {}
    for s in snapshots:
        snap_by_ep.setdefault(s.episode_id, []).append(s)
    payloads = [
        (ep.model_dump_json(),
         _json.dumps([s.model_dump_json() for s in snap_by_ep.get(ep.id, [])]),
         iv.model_dump_json(), n_repro)
        for ep, iv in candidates
    ]
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker,
                             initargs=(str(blobs_root), str(scratch_root),
                                       verify_argv)) as pool:
        return [CausalUnit.model_validate_json(r)
                for r in pool.map(_validate_one, payloads)]
