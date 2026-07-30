"""Recorded and paired counterfactual replay.

- Recorded replay re-executes an episode's recorded actions from a
  snapshot; LLM responses are never re-queried (they live in the trace).
  Matching observation digests + outcome establish determinism.
- Paired replay forks the pre-intervention snapshot into two branches:
  the original branch (determinism control) and the intervened branch.
  A validated flip requires the control to reproduce the original failure
  AND the intervened branch to succeed.

Evidence ladder produced here:
SUGGESTED -> COUNTERFACTUAL_VALIDATED (one flip) -> REPRODUCIBLE (n/n flips).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from causeforge.interventions.apply import apply_intervention
from causeforge.replay.sandbox import LocalSandbox
from causeforge.runtime.tools import ToolExecutor, ToolRegistry
from causeforge.runtime.verifier import PytestVerifier
from causeforge.sdk.schemas import (
    CausalUnit,
    CostLedger,
    Episode,
    EvidenceTier,
    Intervention,
    Outcome,
    ReplayRecord,
    Snapshot,
)


class Replayer:
    def __init__(
        self,
        registry: ToolRegistry,
        sandbox: LocalSandbox,
        verifier: PytestVerifier,
    ):
        self.registry = registry
        self.sandbox = sandbox
        self.verifier = verifier

    # -- internals ----------------------------------------------------------

    def _run_branch(
        self,
        episode: Episode,
        from_step: int,
        tree_digest: str,
        ledger: CostLedger,
        intervention: Optional[Intervention] = None,
    ) -> ReplayRecord:
        workspace = self.sandbox.materialize(tree_digest)
        executor = ToolExecutor(self.registry, mode="replay")
        obs_digests: list[str] = []
        try:
            for step in episode.steps[from_step:]:
                action = step.action
                if intervention is not None and step.index == intervention.target_step:
                    action = apply_intervention(step.action, intervention)
                _, obs_digest = executor.execute(workspace, action, ledger)
                obs_digests.append(obs_digest)
            outcome = self.verifier.evaluate(workspace, ledger)
        finally:
            self.sandbox.dispose(workspace)
        ledger.replay_runs += 1
        branch = "intervened" if intervention is not None else "original"
        record = ReplayRecord(branch=branch, outcome=outcome, obs_digests=obs_digests)
        if intervention is None:
            recorded = [s.obs_digest for s in episode.steps[from_step:]]
            matches = sum(1 for a, b in zip(obs_digests, recorded) if a == b)
            record.digest_match_fraction = matches / len(recorded) if recorded else 1.0
            record.deterministic_match = (
                obs_digests == recorded
                and episode.outcome is not None
                and outcome.signature() == episode.outcome.signature()
            )
        return record

    def _snapshot_for(self, snapshots: list[Snapshot], episode: Episode, step_index: int) -> Snapshot:
        for s in snapshots:
            if s.episode_id == episode.id and s.step_index == step_index:
                return s
        raise KeyError(f"no snapshot for episode {episode.id} step {step_index}")

    # -- public API ---------------------------------------------------------

    def recorded_replay(
        self, episode: Episode, snapshots: list[Snapshot], from_step: int = 0
    ) -> ReplayRecord:
        snap = self._snapshot_for(snapshots, episode, from_step)
        ledger = CostLedger()
        record = self._run_branch(episode, from_step, snap.tree_digest, ledger)
        return record

    def intervened_flip(
        self,
        episode: Episode,
        snapshots: list[Snapshot],
        intervention: Intervention,
        ledger: CostLedger,
    ) -> Outcome:
        """Single intervened-branch run (used by slicing).  Returns outcome."""
        snap = self._snapshot_for(snapshots, episode, intervention.target_step)
        rec = self._run_branch(
            episode, intervention.target_step, snap.tree_digest, ledger, intervention
        )
        return rec.outcome

    def paired_replay(
        self,
        episode: Episode,
        snapshots: list[Snapshot],
        intervention: Intervention,
        n_repro: int = 3,
    ) -> CausalUnit:
        assert episode.outcome is not None, "episode must be verified before replay"
        unit = CausalUnit(
            episode_id=episode.id,
            task_id=episode.task_id,
            intervention=intervention,
            original_outcome=episode.outcome,
        )
        snap = self._snapshot_for(snapshots, episode, intervention.target_step)

        # Branch A: determinism control.
        control = self._run_branch(
            episode, intervention.target_step, snap.tree_digest, unit.cost
        )
        unit.original_replay_match = control.deterministic_match
        unit.control_digest_match = control.digest_match_fraction
        if not control.deterministic_match:
            unit.tier = EvidenceTier.SUGGESTED
            return unit

        # Branch B: intervened, first validation run.
        first = self._run_branch(
            episode, intervention.target_step, snap.tree_digest, unit.cost, intervention
        )
        unit.intervened_outcome = first.outcome
        flipped_once = (not episode.outcome.success) and first.outcome.success
        unit.flipped = flipped_once
        if not flipped_once:
            unit.tier = EvidenceTier.SUGGESTED
            return unit
        unit.tier = EvidenceTier.COUNTERFACTUAL_VALIDATED

        # Reproducibility runs: fresh forks, same intervention.
        flips = 1
        for _ in range(max(0, n_repro - 1)):
            rec = self._run_branch(
                episode, intervention.target_step, snap.tree_digest, unit.cost, intervention
            )
            if (not episode.outcome.success) and rec.outcome.success:
                flips += 1
        unit.repro_runs = n_repro
        unit.repro_flips = flips
        if flips == n_repro:
            unit.tier = EvidenceTier.REPRODUCIBLE
        return unit
