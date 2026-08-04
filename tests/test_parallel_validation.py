"""Parallel validation must agree with serial validation exactly."""

from causal_data_juicer.acquisition.parallel import validate_parallel
from causal_data_juicer.acquisition.screener import Screener, TableFixSource
from causal_data_juicer.pipeline import run_demo  # noqa: F401 (env sanity)
from causal_data_juicer.runtime.agent import ScriptedPolicy
from causal_data_juicer.runtime.collector import Collector
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import PytestVerifier
from causal_data_juicer.sdk.schemas import EvidenceTier
from causal_data_juicer.store.blob import BlobStore
from causal_data_juicer.workloads import toy


def test_parallel_matches_serial(tmp_path, replayer):
    blobs = BlobStore(tmp_path / "blobs")
    collector = Collector(default_registry(), blobs, PytestVerifier())
    episodes, snapshots = [], []
    tasks = toy.build_tasks()
    for task in tasks:
        ws = tmp_path / "ws" / task.id
        task.setup(ws)
        ep, snaps = collector.run_episode(
            task.id, task.description, ws, ScriptedPolicy(task.script)
        )
        episodes.append(ep)
        snapshots.extend(snaps)
    candidates = Screener([TableFixSource(toy.fix_table(tasks))]).screen(episodes)
    assert len(candidates) == 7

    units = validate_parallel(
        candidates, snapshots, blobs.root, tmp_path / "scratch", n_repro=2, workers=4
    )
    assert len(units) == 7
    validated = [u for u in units if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED]
    assert len(validated) == 6  # same as the serial demo
    assert all(u.original_replay_match for u in units)
    assert all(u.repro_flips == u.repro_runs == 2 for u in validated)
