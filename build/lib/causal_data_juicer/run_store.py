"""Run directory persistence.

A run directory is self-contained and re-executable:

    runs/<name>/
      episodes.jsonl    all collected episodes
      snapshots.jsonl   snapshot metadata (trees live in blobs/)
      units.jsonl       causal units with evidence tiers
      report.json       headline numbers + cost ledger
      blobs/            content-addressed workspace trees
      exports/          sft/dpo/memory/regression views + test_regression.py
"""
from __future__ import annotations

import json
from pathlib import Path

from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.replay.sandbox import LocalSandbox
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import PytestVerifier
from causal_data_juicer.sdk.schemas import CausalUnit, CostLedger, Episode, Intervention, Snapshot
from causal_data_juicer.store.blob import BlobStore


def _dump_jsonl(path: Path, models) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for m in models:
            f.write(m.model_dump_json() + "\n")


def _load_jsonl(path: Path, cls):
    if not path.exists():
        return []
    return [cls.model_validate_json(line) for line in path.open() if line.strip()]


class RunStore:
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.blobs = BlobStore(self.run_dir / "blobs")

    # -- save ---------------------------------------------------------------

    def save(self, episodes: list[Episode], snapshots: list[Snapshot],
             units: list[CausalUnit], report: dict) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        _dump_jsonl(self.run_dir / "episodes.jsonl", episodes)
        _dump_jsonl(self.run_dir / "snapshots.jsonl", snapshots)
        _dump_jsonl(self.run_dir / "units.jsonl", units)
        (self.run_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))

    # -- load ---------------------------------------------------------------

    def load_episodes(self) -> list[Episode]:
        return _load_jsonl(self.run_dir / "episodes.jsonl", Episode)

    def load_snapshots(self) -> list[Snapshot]:
        return _load_jsonl(self.run_dir / "snapshots.jsonl", Snapshot)

    def load_units(self) -> list[CausalUnit]:
        return _load_jsonl(self.run_dir / "units.jsonl", CausalUnit)

    def load_report(self) -> dict:
        return json.loads((self.run_dir / "report.json").read_text())

    # -- regression replay --------------------------------------------------

    def replay_regression_case(self, case: dict, scratch: Path) -> tuple[bool, str]:
        """Re-execute one exported counterfactual case; True iff the flip
        (original fails, intervened succeeds) reproduces."""
        episodes = {ep.id: ep for ep in self.load_episodes()}
        snapshots = self.load_snapshots()
        episode = episodes.get(case["episode_id"])
        if episode is None:
            return False, f"episode {case['episode_id']} not found"
        intervention = Intervention.model_validate(case["intervention"])
        replayer = Replayer(
            default_registry(),
            LocalSandbox(self.blobs, Path(scratch)),
            PytestVerifier(),
        )
        ledger = CostLedger()
        control = replayer.recorded_replay(episode, snapshots, intervention.target_step)
        if control.outcome.success != case["expected"]["original_success"]:
            return False, f"control branch outcome changed: {control.outcome.detail}"
        outcome = replayer.intervened_flip(episode, snapshots, intervention, ledger)
        if outcome.success != case["expected"]["intervened_success"]:
            return False, f"intervened branch did not flip: {outcome.detail}"
        return True, "flip reproduced"
