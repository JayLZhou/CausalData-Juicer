"""Analysis and shaping operators — observational, zero budget.

These never execute an environment, so they can neither raise nor forge an
evidence tier: they select, deduplicate, sample, and report on what the
interventional operators produced.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from causal_data_juicer.ops.base_op import OPERATORS, ObservationalOp, OpContext


@OPERATORS.register("filter_units")
class FilterUnits(ObservationalOp):
    """Keep units matching a predicate. Params: min_tier (e.g. MINIMAL),
    flipped (bool), task_prefix (str), source (str). Unset params do not
    constrain."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.sdk.schemas import EvidenceTier

        min_tier = self.params.get("min_tier")
        want_flipped = self.params.get("flipped")
        prefix = self.params.get("task_prefix")
        source = self.params.get("source")

        def keep(u) -> bool:
            if min_tier is not None and u.tier < EvidenceTier[str(min_tier)]:
                return False
            if want_flipped is not None and bool(u.flipped) != bool(want_flipped):
                return False
            if prefix is not None and not str(u.task_id).startswith(str(prefix)):
                return False
            return not (source is not None and u.effective_intervention().source != source)

        before = len(ctx.units)
        ctx.units = [u for u in ctx.units if keep(u)]
        ctx.meta.setdefault("filter_units", []).append({"before": before, "after": len(ctx.units)})
        return ctx


@OPERATORS.register("dedupe_units")
class DedupeUnits(ObservationalOp):
    """Drop units whose (episode, target step, effect) signature repeats —
    two fixes that flip the same failure the same way are one datum.
    Params: none."""

    def run(self, ctx: OpContext) -> OpContext:
        seen: set[str] = set()
        kept = []
        for u in ctx.units:
            iv = u.effective_intervention()
            outcome = u.intervened_outcome
            sig = hashlib.sha256(
                json.dumps(
                    {
                        "episode": u.episode_id,
                        "step": iv.target_step,
                        "type": str(iv.type),
                        "passed": None if outcome is None else outcome.passed,
                        "success": None if outcome is None else outcome.success,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()[:16]
            if sig in seen:
                continue
            seen.add(sig)
            kept.append(u)
        ctx.meta.setdefault("dedupe_units", []).append(
            {"before": len(ctx.units), "after": len(kept)}
        )
        ctx.units = kept
        return ctx


@OPERATORS.register("sample_units")
class SampleUnits(ObservationalOp):
    """Deterministically subsample units (stable across runs — the digest of
    the unit id decides). Params: n (required), seed (default 0)."""

    def run(self, ctx: OpContext) -> OpContext:
        n = int(self.params["n"])
        seed = str(self.params.get("seed", 0))

        def rank(u) -> str:
            return hashlib.sha256(f"{seed}:{u.id}".encode()).hexdigest()

        ctx.units = sorted(ctx.units, key=rank)[:n]
        return ctx


@OPERATORS.register("dag_stats")
class DagStats(ObservationalOp):
    """Trace-DAG sharing statistics (unique trees, bytes saved) into
    ctx.meta['dag']. Params: none."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.ops.base_op import engine_services
        from causal_data_juicer.store.dag import dag_stats

        blobs = engine_services(ctx)["blobs"]
        ctx.meta["dag"] = dag_stats(ctx.episodes, ctx.snapshots, blobs.root)
        return ctx


@OPERATORS.register("cost_report")
class CostReport(ObservationalOp):
    """Ledger breakdown plus cost per validated unit into ctx.meta['cost'].
    Params: out (optional path, relative to workdir)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.sdk.schemas import EvidenceTier

        validated = [u for u in ctx.units if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED]
        led = ctx.ledger
        report = {
            "llm_calls": led.llm_calls,
            "tokens_in": led.tokens_in,
            "tokens_out": led.tokens_out,
            "tool_calls": led.tool_calls,
            "replay_runs": led.replay_runs,
            "wall_time_s": round(led.wall_time_s, 2),
            "dollars": round(led.dollars, 4),
            "validated_units": len(validated),
            "replays_per_validated_unit": (
                round(led.replay_runs / len(validated), 2) if validated else None
            ),
            "seconds_per_validated_unit": (
                round(led.wall_time_s / len(validated), 2) if validated else None
            ),
        }
        ctx.meta["cost"] = report
        if self.params.get("out"):
            path = ctx.workdir / str(self.params["out"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=1))
            ctx.exports["cost_report"] = str(path)
        return ctx


@OPERATORS.register("coverage_report")
class CoverageReport(ObservationalOp):
    """How much of the failure set got covered, by task and by tier, into
    ctx.meta['coverage']. Params: out (optional path)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.sdk.schemas import EvidenceTier

        failed = {e.task_id for e in ctx.episodes if e.outcome and not e.outcome.success}
        covered = {u.task_id for u in ctx.units if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED}
        report = {
            "failed_tasks": len(failed),
            "covered_tasks": len(covered & failed),
            "coverage": round(len(covered & failed) / len(failed), 3) if failed else None,
            "uncovered": sorted(failed - covered),
            "units_by_tier": dict(Counter(u.tier_name for u in ctx.units)),
        }
        ctx.meta["coverage"] = report
        if self.params.get("out"):
            path = Path(ctx.workdir) / str(self.params["out"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=1))
            ctx.exports["coverage_report"] = str(path)
        return ctx
