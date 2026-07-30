"""M2 evaluation: cost-per-unit curves for acquisition policies.

Candidates are pooled from existing run directories (the heterogeneous
7B+14B fixer pool, per finding A10): the base run supplies episodes,
snapshots and blobs; pool runs contribute their candidate interventions
remapped onto base episodes by task_id (trajectories are identical
because agent responses were replayed from the shared LLM cache).

Cost trick: none of the shipped policies read the budget — a budget only
truncates the execution sequence.  So each policy runs ONCE with an
unlimited budget and every matched-budget point is read off its curve,
instead of re-running per budget.
"""
from __future__ import annotations

import json
from pathlib import Path

from causeforge.acquisition.budget import Budget
from causeforge.acquisition.engine import AcquisitionEngine, AcquisitionResult
from causeforge.acquisition.policies import Candidate, make_policy
from causeforge.replay.replayer import Replayer
from causeforge.replay.sandbox import LocalSandbox
from causeforge.runtime.tools import default_registry
from causeforge.runtime.verifier import PytestVerifier
from causeforge.run_store import RunStore


def load_pooled_candidates(base_dir: Path, pool_dirs: list[Path]):
    base = RunStore(base_dir)
    episodes = base.load_episodes()
    snapshots = base.load_snapshots()
    by_task = {ep.task_id: ep for ep in episodes}

    candidates: list[Candidate] = []
    seen: set[str] = set()

    def add(episode, intervention, source_tag):
        iv = intervention.model_copy(deep=True)
        if not iv.source or source_tag not in iv.source:
            iv.source = f"{iv.source or 'fixer'}@{source_tag}"
        key = f"{episode.id}:{iv.effect_signature()}"
        if key in seen:
            return
        step = episode.steps[iv.target_step] if iv.target_step < len(episode.steps) else None
        if step is None or step.action.tool != "write_file":
            return  # trajectory mismatch — cannot remap this candidate
        seen.add(key)
        candidates.append(Candidate(episode=episode, intervention=iv))

    for unit in base.load_units():
        add(by_task[unit.task_id], unit.intervention, base_dir.name)
    for pool_dir in pool_dirs:
        for unit in RunStore(pool_dir).load_units():
            ep = by_task.get(unit.task_id)
            if ep is not None:
                add(ep, unit.intervention, Path(pool_dir).name)
    return base, episodes, snapshots, candidates


def evaluate(
    base_dir: Path,
    pool_dirs: list[Path],
    policies: list[str],
    budgets: list[int],
    n_repro: int = 3,
    scratch: Path | None = None,
) -> dict:
    base, episodes, snapshots, candidates = load_pooled_candidates(base_dir, pool_dirs)
    scratch = scratch or (Path(base_dir) / "scratch-m2")
    replayer = Replayer(default_registry(), LocalSandbox(base.blobs, scratch),
                        PytestVerifier(timeout=120))
    engine = AcquisitionEngine(replayer, n_repro=n_repro)

    results: list[AcquisitionResult] = []
    for spec in policies:
        if spec.endswith("[no-mech]"):
            bare = AcquisitionEngine(replayer, n_repro=n_repro, mechanisms=False)
            result = bare.run(list(candidates), snapshots, Budget(),
                              make_policy(spec.removesuffix("[no-mech]")))
            result.policy = spec
        else:
            result = engine.run(list(candidates), snapshots, Budget(), make_policy(spec))
        results.append(result)

    def at_budget(curve, max_replays):
        best = {"replays": 0, "seconds": 0, "validated_units": 0, "distinct_tasks": 0}
        for point in curve:
            if point["replays"] <= max_replays:
                best = point
            else:
                break
        return best

    table = []
    for r in results:
        row = {"policy": r.policy,
               "candidates": f"{r.candidates_processed}/{r.candidates_total}",
               "total": {"replays": r.spent.replay_runs,
                         "validated_units": len(r.validated()),
                         "distinct_tasks": r.distinct_tasks()},
               "at_budget": {str(b): at_budget(r.curve, b) for b in budgets}}
        table.append(row)

    return {
        "base_run": str(base_dir),
        "pool_runs": [str(p) for p in pool_dirs],
        "n_candidates": len(candidates),
        "n_repro": n_repro,
        "budgets": budgets,
        "results": table,
        "curves": {r.policy: r.curve for r in results},
    }


def print_eval(report: dict) -> None:
    budgets = report["budgets"]
    print(f"pooled candidates: {report['n_candidates']}  (n_repro={report['n_repro']})")
    header = f"{'policy':<12}" + "".join(f"@{b:<11}" for b in budgets) + "total (replays)"
    print(header)
    for row in report["results"]:
        cells = ""
        for b in budgets:
            p = row["at_budget"][str(b)]
            cells += f"{p['validated_units']}u/{p['distinct_tasks']}t     "[:12]
        total = row["total"]
        print(f"{row['policy']:<12}{cells}{total['validated_units']}u/{total['distinct_tasks']}t "
              f"({total['replays']})")
    print("(u = validated units, t = distinct tasks covered, @N = replay budget N)")
