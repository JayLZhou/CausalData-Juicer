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

from causal_data_juicer.interventions.apply import apply_intervention
from causal_data_juicer.replay.sandbox import UnsafeLocalWorkspace
from causal_data_juicer.runtime.tools import ToolExecutor, ToolRegistry
from causal_data_juicer.runtime.verifier import PytestVerifier
from causal_data_juicer.sdk.schemas import (
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
        sandbox: UnsafeLocalWorkspace,
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
        intervention: Intervention | None = None,
        prep=None,  # callable(workspace) applied after fork, e.g. env-pointer override (M4)
        continuation_policy=None,  # reactive replay: downstream re-generates live
    ) -> ReplayRecord:
        workspace = self.sandbox.materialize(tree_digest)
        if prep is not None:
            prep(workspace)
        executor = ToolExecutor(self.registry, mode="replay")
        obs_digests: list[str] = []
        live_steps: list = []
        try:
            for step in episode.steps[from_step:]:
                action = step.action
                if intervention is not None and step.index == intervention.target_step:
                    action = apply_intervention(step.action, intervention)
                obs, obs_digest = executor.execute(workspace, action, ledger)
                obs_digests.append(obs_digest)
                if (
                    continuation_policy is not None
                    and intervention is not None
                    and step.index == intervention.target_step
                ):
                    # Reactive continuation: from here on, downstream agents
                    # RE-REACT to the intervened state instead of replaying
                    # recorded actions — the message-credit semantics.
                    from causal_data_juicer.sdk.schemas import Step as _Step

                    live_steps.append(
                        _Step(
                            index=step.index, action=action, observation=obs, obs_digest=obs_digest
                        )
                    )
                    idx = step.index + 1
                    while True:
                        nxt = continuation_policy.next_action(episode.task_id, idx, live_steps)
                        if nxt is None:
                            break
                        live_action, llm = nxt
                        live_obs, live_digest = executor.execute(workspace, live_action, ledger)
                        if llm is not None and not llm.cached:
                            ledger.charge_llm(llm.tokens_in, llm.tokens_out, dollars=llm.dollars)
                        live_steps.append(
                            _Step(
                                index=idx,
                                action=live_action,
                                observation=live_obs,
                                obs_digest=live_digest,
                            )
                        )
                        idx += 1
                    break
            outcome = self.verifier.evaluate(workspace, ledger)
        finally:
            self.sandbox.dispose(workspace)
        ledger.replay_runs += 1
        branch = "intervened" if intervention is not None else "original"
        record = ReplayRecord(branch=branch, outcome=outcome, obs_digests=obs_digests)
        if intervention is None:
            recorded = [s.obs_digest for s in episode.steps[from_step:]]
            matches = sum(1 for a, b in zip(obs_digests, recorded, strict=False) if a == b)
            record.digest_match_fraction = matches / len(recorded) if recorded else 1.0
            record.deterministic_match = (
                obs_digests == recorded
                and episode.outcome is not None
                and outcome.signature() == episode.outcome.signature()
            )
        return record

    def fork_at(
        self,
        episode: Episode,
        snapshots: list[Snapshot],
        step: int,
        ledger: CostLedger | None = None,
        prep=None,
    ):
        """Materialize the state *before* ``step`` from a possibly sparse
        checkpoint set: restore the nearest checkpoint at or before the
        step and re-execute the recorded prefix in between (M3).

        Returns (workspace, prefix_steps_reexecuted).  Caller disposes."""
        avail = [s for s in snapshots if s.episode_id == episode.id and s.step_index <= step]
        if not avail:
            raise KeyError(f"no checkpoint at or before step {step} for {episode.id}")
        snap = max(avail, key=lambda s: s.step_index)
        workspace = self.sandbox.materialize(snap.tree_digest)
        if prep is not None:
            prep(workspace)
        executor = ToolExecutor(self.registry, mode="replay")
        ledger = ledger if ledger is not None else CostLedger()
        n = 0
        for st in episode.steps[snap.step_index : step]:
            executor.execute(workspace, st.action, ledger)
            n += 1
        return workspace, n

    def _snapshot_for(
        self, snapshots: list[Snapshot], episode: Episode, step_index: int
    ) -> Snapshot:
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
        control_cache: dict | None = None,
        early_stop_repro: bool = False,
        prep=None,
        continuation_policy=None,
    ) -> CausalUnit:
        """``control_cache`` (M2 mechanism): memoizes the determinism-control
        branch per (episode, step) so multiple candidates targeting the same
        fork point pay for it once.  ``early_stop_repro`` (M2 mechanism):
        abandon remaining repro runs at the first non-flip, since
        REPRODUCIBLE requires n/n anyway."""
        assert episode.outcome is not None, "episode must be verified before replay"
        unit = CausalUnit(
            episode_id=episode.id,
            task_id=episode.task_id,
            intervention=intervention,
            original_outcome=episode.outcome,
        )
        snap = self._snapshot_for(snapshots, episode, intervention.target_step)

        # Branch A: determinism control (memoized across candidates).
        cache_key = (episode.id, intervention.target_step)
        if control_cache is not None and cache_key in control_cache:
            control = control_cache[cache_key]
        else:
            control = self._run_branch(
                episode, intervention.target_step, snap.tree_digest, unit.cost, prep=prep
            )
            if control_cache is not None:
                control_cache[cache_key] = control
        unit.original_replay_match = control.deterministic_match
        unit.control_digest_match = control.digest_match_fraction
        if not control.deterministic_match:
            unit.tier = EvidenceTier.SUGGESTED
            return unit

        # Branch B: intervened, first validation run.
        first = self._run_branch(
            episode,
            intervention.target_step,
            snap.tree_digest,
            unit.cost,
            intervention,
            prep=prep,
            continuation_policy=continuation_policy,
        )
        unit.intervened_outcome = first.outcome
        flipped_once = (not episode.outcome.success) and first.outcome.success
        unit.flipped = flipped_once
        if not flipped_once:
            unit.tier = EvidenceTier.SUGGESTED
            return unit
        unit.tier = EvidenceTier.COUNTERFACTUAL_VALIDATED

        # Reproducibility runs: fresh forks, same intervention.
        flips, runs = 1, 1
        for _ in range(max(0, n_repro - 1)):
            rec = self._run_branch(
                episode,
                intervention.target_step,
                snap.tree_digest,
                unit.cost,
                intervention,
                prep=prep,
                continuation_policy=continuation_policy,
            )
            runs += 1
            if (not episode.outcome.success) and rec.outcome.success:
                flips += 1
            elif early_stop_repro:
                break
        unit.repro_runs = n_repro if flips == runs else runs
        unit.repro_flips = flips
        if flips == n_repro:
            unit.tier = EvidenceTier.REPRODUCIBLE
        return unit
