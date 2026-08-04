"""Engine operators — capabilities that existed only behind the CLI.

Parallel validation, budgeted scheduling, the stress direction, selective
revalidation and the report writer were all reachable as Python or as
`cdj` subcommands but not as recipe vocabulary, which is why the zoo
undersold what the engine can do.
"""

from __future__ import annotations

import json
from pathlib import Path

from causal_data_juicer.ops.base_op import (
    OPERATORS,
    CompileOp,
    InterventionalOp,
    ObservationalOp,
    OpContext,
    SourceOp,
    engine_services,
)

# ------------------------------- sources -----------------------------------


@OPERATORS.register("fix_table")
class FixTable(SourceOp):
    """Curated / cached fixes as a candidate source — the zero-cost way to
    replay a known set of corrections. Params: path (JSON
    {task_id: [{tool, args}, …]})."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.acquisition.screener import TableFixSource
        from causal_data_juicer.sdk.schemas import Intervention, InterventionType, ToolCall

        raw = json.loads(Path(str(self.params["path"])).read_text())
        table: dict[str, list] = {}
        for task_id, entries in raw.items():
            table[task_id] = [
                Intervention(
                    type=InterventionType.ACTION_REPLACE,
                    target_step=int(e.get("target_step", 0)),
                    new_action=ToolCall(tool=e["tool"], args=e["args"]),
                    rationale=e.get("rationale", "curated fix"),
                    source="fix-table",
                )
                for e in entries
            ]
        ctx.sources.append(TableFixSource(table))
        return ctx


@OPERATORS.register("refine")
class Refine(SourceOp):
    """Validation-in-the-loop: revise the interventions that did NOT flip,
    conditioning on their own executed failure output. Requires units from
    a previous paired_replay. Params: base_url, model, rounds (default 1)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.acquisition.fixer import propose_refinement
        from causal_data_juicer.runtime.llm import DiskCachedLLM, OpenAICompatClient

        llm = DiskCachedLLM(
            OpenAICompatClient(self.params["base_url"], self.params["model"]),
            ctx.workdir / "llm_cache",
        )
        eps = {e.id: e for e in ctx.episodes}
        rounds = int(self.params.get("rounds", 1))
        proposed = 0
        for unit in ctx.units:
            if unit.flipped or unit.intervened_outcome is None:
                continue
            ep = eps.get(unit.episode_id)
            if ep is None:
                continue
            revised = propose_refinement(
                llm,
                ep,
                unit.effective_intervention(),
                unit.intervened_outcome.detail,
                rounds,
                ledger=ctx.ledger,
            )
            if revised is not None:
                ctx.candidates.append((ep, revised))
                proposed += 1
        ctx.meta["refine"] = {"proposed": proposed}
        return ctx


# ---------------------------- interventional -------------------------------


@OPERATORS.register("paired_replay_parallel")
class PairedReplayParallel(InterventionalOp):
    """paired_replay across a process pool — identical outputs, wall-clock
    divided by the worker count (the per-worker control caches duplicate
    some replays; cost_report will show it). Params: workers (default 4),
    n_repro (default 3)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.acquisition.parallel import validate_parallel
        from causal_data_juicer.maintenance.provenance import env_fingerprint, stamp

        services = engine_services(ctx)
        units = validate_parallel(
            list(ctx.candidates),
            ctx.snapshots,
            services["blobs"].root,
            ctx.workdir / "scratch-parallel",
            n_repro=int(self.params.get("n_repro", 3)),
            workers=int(self.params.get("workers", 4)),
        )
        fingerprint = env_fingerprint(services["tool_registry"], "recipe")
        for unit in units:
            stamp(unit, fingerprint)
            ctx.units.append(unit)
            ctx.ledger.merge(unit.cost)
        ctx.candidates.clear()
        return ctx


@OPERATORS.register("stress_probe")
class StressProbe(InterventionalOp):
    """The stress direction: run each candidate as a single intervened branch
    against a *passing* episode and record whether it breaks the outcome —
    critical vs harmless, same machinery, opposite sign. Params: none."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.sdk.schemas import CausalUnit, EvidenceTier

        services = engine_services(ctx)
        snaps = ctx.snapshots
        for ep, iv in list(ctx.candidates):
            snap = next(
                (s for s in snaps if s.episode_id == ep.id and s.step_index == iv.target_step),
                None,
            )
            if snap is None:
                continue
            ledger = ctx.ledger
            outcome = services["replayer"].intervened_flip(ep, snaps, iv, ledger)
            unit = CausalUnit(
                episode_id=ep.id,
                task_id=ep.task_id,
                intervention=iv,
                original_outcome=ep.outcome,
                intervened_outcome=outcome,
                flipped=bool(ep.outcome and ep.outcome.success and not outcome.success),
                tier=EvidenceTier.COUNTERFACTUAL_VALIDATED,
            )
            ctx.units.append(unit)
        ctx.candidates.clear()
        return ctx


@OPERATORS.register("budget_screen")
class BudgetScreen(InterventionalOp):
    """Validate candidates under a hard budget with a pluggable acquisition
    policy — the "budgeted" half of the engine, exposed. Params: policy
    (exhaustive | random | adaptive, default adaptive), replays (budget,
    default 60), n_repro (default 3)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.acquisition.budget import Budget
        from causal_data_juicer.acquisition.engine import AcquisitionEngine
        from causal_data_juicer.acquisition.policies import Candidate, make_policy

        services = engine_services(ctx)
        engine = AcquisitionEngine(services["replayer"], n_repro=int(self.params.get("n_repro", 3)))
        candidates = [Candidate(episode=ep, intervention=iv) for ep, iv in ctx.candidates]
        budget = Budget(max_replays=int(self.params.get("replays", 60)))
        result = engine.run(
            candidates,
            ctx.snapshots,
            budget,
            make_policy(str(self.params.get("policy", "adaptive"))),
        )
        ctx.units.extend(result.units)
        for unit in result.units:
            ctx.ledger.merge(unit.cost)
        ctx.meta["budget_screen"] = {
            "policy": result.policy,
            "budget": result.budget,
            "candidates_total": result.candidates_total,
            "validated": len(result.units),
        }
        ctx.candidates.clear()
        return ctx


@OPERATORS.register("revalidate")
class Revalidate(InterventionalOp):
    """Selective revalidation under a dependency event: only units whose
    claims intersect the change are replayed, inside the NEW environment;
    survivors are re-stamped, casualties demoted. Params: family (required),
    python (required, interpreter of the new env), freeze (required, the new
    `pip freeze` text), mode (selective | full, default selective),
    n_repro (default 2)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.maintenance.revalidate import revalidate

        services = engine_services(ctx)
        old_freezes = ctx.meta.get("env_freezes", {})
        report = revalidate(
            ctx.units,
            ctx.episodes,
            ctx.snapshots,
            services["replayer"],
            changed_family=str(self.params["family"]),
            new_env_python=Path(str(self.params["python"])),
            new_env_freeze=str(self.params["freeze"]),
            old_freezes=old_freezes,
            mode=str(self.params.get("mode", "selective")),
            n_repro=int(self.params.get("n_repro", 2)),
        )
        ctx.meta["revalidate"] = report if isinstance(report, dict) else {"result": str(report)}
        return ctx


# ----------------------- observational / compile ---------------------------


@OPERATORS.register("export_observational")
class ExportObservational(ObservationalOp):
    """Behaviour-cloning and failure-log views straight from episodes — the
    OBSERVED-ceiling exports that need no replay at all. Params: none."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.compiler.observational import compile_observational

        for name, path in compile_observational(
            ctx.episodes, Path(ctx.workdir) / "exports"
        ).items():
            ctx.exports[name] = str(path)
        return ctx


@OPERATORS.register("report")
class Report(CompileOp):
    """Write the human-readable report for this recipe run (terminal text and
    optional HTML), so a recipe ends with something a person can read.
    Params: html (bool, default false)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.report import explain_html, explain_text

        if not (Path(ctx.workdir) / "units.jsonl").exists():
            OPERATORS.get("save_run")().run(ctx)
        text = explain_text(Path(ctx.workdir))
        (Path(ctx.workdir) / "report.txt").write_text(text)
        ctx.exports["report_txt"] = str(Path(ctx.workdir) / "report.txt")
        if self.params.get("html"):
            path = explain_html(Path(ctx.workdir), Path(ctx.workdir) / "report.html")
            ctx.exports["report_html"] = str(path)
        ctx.meta["report"] = text.splitlines()[:3]
        return ctx
