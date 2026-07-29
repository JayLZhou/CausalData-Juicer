"""End-to-end M1 pipeline:

collect -> verify -> screen -> paired counterfactual replay ->
reproducibility runs -> minimal causal slicing -> provenance stamping ->
compile SFT / DPO / memory / regression views -> report.

The headline number is flip reproducibility on the deterministic subset
(kill line: >= 90%).  All costs are charged to ledgers from line one.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from causeforge.acquisition.screener import Screener, TableFixSource
from causeforge.compiler.exports import compile_all
from causeforge.maintenance.provenance import env_fingerprint, stamp
from causeforge.replay.replayer import Replayer
from causeforge.replay.sandbox import LocalSandbox
from causeforge.runtime.agent import ScriptedPolicy
from causeforge.runtime.collector import Collector
from causeforge.runtime.tools import default_registry
from causeforge.runtime.verifier import PytestVerifier
from causeforge.run_store import RunStore
from causeforge.sdk.schemas import CausalUnit, CostLedger, Episode, EvidenceTier, Snapshot
from causeforge.slicing.ddmin import minimize_unit
from causeforge.workloads import toy


def run_demo(run_dir: Path, n_repro: int = 3, keep_workspaces: bool = False) -> dict:
    t_start = time.monotonic()
    run_dir = Path(run_dir)
    if run_dir.exists():
        shutil.rmtree(run_dir)
    store = RunStore(run_dir)
    registry = default_registry()
    verifier = PytestVerifier()
    collector = Collector(registry, store.blobs, verifier)
    sandbox = LocalSandbox(store.blobs, run_dir / "scratch")
    replayer = Replayer(registry, sandbox, verifier)

    tasks = toy.build_tasks()
    fingerprint = env_fingerprint(registry, toy.WORKLOAD_ID)
    fingerprint["workload_digest"] = toy.workload_digest(tasks)

    # 1) collect
    episodes: list[Episode] = []
    snapshots: list[Snapshot] = []
    ws_root = run_dir / "workspaces"
    for task in tasks:
        ws = ws_root / task.id
        task.setup(ws)
        policy = ScriptedPolicy(task.script)
        ep, snaps = collector.run_episode(
            task.id, task.description, ws, policy, workload_id=toy.WORKLOAD_ID
        )
        episodes.append(ep)
        snapshots.extend(snaps)
    failures = [ep for ep in episodes if ep.outcome and not ep.outcome.success]

    # 2) screen candidates (cached fixer-table source, zero live tokens)
    screener = Screener(sources=[TableFixSource(toy.fix_table(tasks))])
    candidates = screener.screen(episodes)

    # 3) paired replay + reproducibility + slicing
    units: list[CausalUnit] = []
    for ep, iv in candidates:
        unit = replayer.paired_replay(ep, snapshots, iv, n_repro=n_repro)
        if unit.tier >= EvidenceTier.REPRODUCIBLE:
            unit = minimize_unit(replayer, ep, snapshots, unit)
        stamp(unit, fingerprint)
        units.append(unit)

    # 4) compile the four views
    exports = compile_all(units, episodes, run_dir / "exports")

    # 5) report
    flipped = [u for u in units if u.flipped]
    repro_runs = sum(u.repro_runs for u in flipped)
    repro_flips = sum(u.repro_flips for u in flipped)
    flip_repro_rate = repro_flips / repro_runs if repro_runs else None
    total_cost = CostLedger()
    for ep in episodes:
        total_cost.merge(ep.cost)
    for u in units:
        total_cost.merge(u.cost)
    total_cost.wall_time_s = round(total_cost.wall_time_s, 2)
    validated = [u for u in units if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED]

    report = {
        "workload": toy.WORKLOAD_ID,
        "episodes": len(episodes),
        "failed_episodes": len(failures),
        "candidates_screened": len(candidates),
        "units_by_tier": {
            tier.name: sum(1 for u in units if u.tier == tier)
            for tier in EvidenceTier
            if any(u.tier == tier for u in units)
        },
        "validated_units": len(validated),
        "flip_repro_rate": flip_repro_rate,
        "flip_repro_detail": f"{repro_flips}/{repro_runs} intervened replays flipped",
        "determinism_control_ok": all(u.original_replay_match for u in units),
        "slicing": {
            "atoms_before": sum(u.atoms_before_slicing for u in validated),
            "atoms_after": sum(u.atoms_after_slicing for u in validated),
        },
        "cost": total_cost.model_dump(),
        "cost_per_validated_unit_s": (
            round(sum(u.cost.wall_time_s for u in validated) / len(validated), 2)
            if validated else None
        ),
        "exports": {k: str(v) for k, v in exports.items()},
        "provenance": fingerprint,
        "wall_time_total_s": round(time.monotonic() - t_start, 2),
    }
    store.save(episodes, snapshots, units, report)
    if not keep_workspaces:
        shutil.rmtree(run_dir / "scratch", ignore_errors=True)
    return report
