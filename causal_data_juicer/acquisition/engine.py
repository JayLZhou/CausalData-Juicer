"""Budgeted acquisition engine (M2).

Runs candidate validation under a hard budget with a pluggable policy on
top of the always-on mechanism layer:

  - control-branch memoization (shared per fork point),
  - early repro stop (first non-flip abandons the remaining runs),
  - slicing only for units that reached REPRODUCIBLE.

Every candidate processed appends a point to the curve trace
(cost so far vs validated units so far) — the raw material for the
cost-per-unit comparison across policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from causal_data_juicer.acquisition.budget import Budget
from causal_data_juicer.acquisition.policies import AcquisitionPolicy, Candidate
from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.sdk.schemas import CausalUnit, CostLedger, EvidenceTier, Snapshot
from causal_data_juicer.slicing.ddmin import minimize_unit


@dataclass
class AcquisitionResult:
    policy: str
    budget: str
    units: list[CausalUnit] = field(default_factory=list)
    spent: CostLedger = field(default_factory=CostLedger)
    curve: list[dict] = field(default_factory=list)
    candidates_processed: int = 0
    candidates_total: int = 0

    def validated(self) -> list[CausalUnit]:
        return [u for u in self.units if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED]

    def distinct_tasks(self) -> int:
        return len({u.task_id for u in self.validated()})


class AcquisitionEngine:
    def __init__(
        self,
        replayer: Replayer,
        n_repro: int = 3,
        slice_minimal: bool = True,
        mechanisms: bool = True,
    ):
        self.replayer = replayer
        self.n_repro = n_repro
        self.slice_minimal = slice_minimal
        self.mechanisms = mechanisms  # ablation switch for the always-on layer

    def run(
        self,
        candidates: list[Candidate],
        snapshots: list[Snapshot],
        budget: Budget,
        policy: AcquisitionPolicy,
    ) -> AcquisitionResult:
        result = AcquisitionResult(
            policy=policy.name, budget=budget.label(), candidates_total=len(candidates)
        )
        pending = list(candidates)
        control_cache: dict | None = {} if self.mechanisms else None

        while pending and not budget.exhausted(result.spent):
            candidate = policy.next(pending)
            if candidate is None:
                break  # policy decided further spend isn't worth it
            pending.remove(candidate)

            unit = self.replayer.paired_replay(
                candidate.episode,
                snapshots,
                candidate.intervention,
                n_repro=self.n_repro,
                control_cache=control_cache,
                early_stop_repro=self.mechanisms,
            )
            if self.slice_minimal and unit.tier >= EvidenceTier.REPRODUCIBLE:
                unit = minimize_unit(self.replayer, candidate.episode, snapshots, unit)
            result.units.append(unit)
            result.spent.merge(unit.cost)
            result.candidates_processed += 1
            policy.observe(candidate, unit)

            result.curve.append(
                {
                    "replays": result.spent.replay_runs,
                    "seconds": round(result.spent.wall_time_s, 2),
                    "validated_units": len(result.validated()),
                    "distinct_tasks": result.distinct_tasks(),
                }
            )
        return result
