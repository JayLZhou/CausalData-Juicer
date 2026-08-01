"""The operator zoo — DJ-style registered wrappers over the engine.

Each op is a thin adapter: the engine stays the engine; recipes get a
uniform vocabulary.
"""
from __future__ import annotations

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


# --------------------------- observational ---------------------------------

@OPERATORS.register("collect_toy")
class CollectToy(ObservationalOp):
    """Collect the built-in toy workload (offline; also seeds the toy fix
    table as a candidate source). Params: none."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.acquisition.screener import TableFixSource
        from causal_data_juicer.runtime.agent import ScriptedPolicy
        from causal_data_juicer.workloads import toy

        services = engine_services(ctx)
        tasks = toy.build_tasks()
        for task in tasks:
            ws = ctx.workdir / "workspaces" / task.id
            task.setup(ws)
            episode, snaps = services["collector"].run_episode(
                task.id, task.description, ws, ScriptedPolicy(task.script),
                workload_id=toy.WORKLOAD_ID)
            ctx.episodes.append(episode)
            ctx.snapshots.extend(snaps)
            ctx.ledger.merge(episode.cost)
        ctx.sources.append(TableFixSource(toy.fix_table(tasks)))
        return ctx


@OPERATORS.register("load_run")
class LoadRun(ObservationalOp):
    """Load a previous run directory into the context. Params: path."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.run_store import RunStore
        store = RunStore(Path(self.params["path"]))
        ctx.episodes.extend(store.load_episodes())
        ctx.snapshots.extend(store.load_snapshots())
        ctx.services["blobs"] = store.blobs  # replays must use this run's blobs
        return ctx


@OPERATORS.register("import_traces")
class ImportTraces(ObservationalOp):
    """Ingest external agent traces (Import Mode; OBSERVED ceiling).
    Params: path."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.runtime.import_trace import load_generic_traces
        ctx.episodes.extend(load_generic_traces(Path(self.params["path"])))
        return ctx


@OPERATORS.register("screen_failures")
class ScreenFailures(ObservationalOp):
    """Select failed episodes and gather deduped candidates from the
    context's sources. Params: none."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.acquisition.screener import Screener
        ctx.candidates.extend(Screener(sources=list(ctx.sources)).screen(ctx.episodes))
        return ctx


# ------------------------------ sources ------------------------------------

@OPERATORS.register("fixer_llm")
class FixerLLM(SourceOp):
    """LLM fixer candidate source. Params: base_url, model,
    candidates (default 2), tests_by_task (optional)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.acquisition.fixer import FixerLLMSource
        from causal_data_juicer.runtime.llm import DiskCachedLLM, OpenAICompatClient
        llm = DiskCachedLLM(
            OpenAICompatClient(self.params["base_url"], self.params["model"]),
            ctx.workdir / "llm_cache")
        ctx.sources.append(FixerLLMSource(
            llm, candidates_per_failure=int(self.params.get("candidates", 2)),
            ledger=ctx.ledger, tests_by_task=self.params.get("tests_by_task")))
        return ctx


@OPERATORS.register("resample")
class Resample(SourceOp):
    """Temperature-resampling candidate source. Params: base_url, model,
    k (default 3), temperature (default 0.85)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.acquisition.resample import ResampleSource
        from causal_data_juicer.runtime.llm import DiskCachedLLM, OpenAICompatClient
        llm = DiskCachedLLM(
            OpenAICompatClient(self.params["base_url"], self.params["model"],
                               temperature=float(self.params.get("temperature", 0.85))),
            ctx.workdir / "llm_cache")
        ctx.sources.append(ResampleSource(llm, k=int(self.params.get("k", 3)),
                                          ledger=ctx.ledger))
        return ctx


# ---------------------------- interventional -------------------------------

@OPERATORS.register("paired_replay")
class PairedReplay(InterventionalOp):
    """Validate every candidate with paired counterfactual replay.
    Params: n_repro (default 3)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.maintenance.provenance import env_fingerprint, stamp
        services = engine_services(ctx)
        fingerprint = env_fingerprint(services["tool_registry"], "recipe")
        control_cache: dict = {}
        for ep, iv in ctx.candidates:
            unit = services["replayer"].paired_replay(
                ep, ctx.snapshots, iv, n_repro=int(self.params.get("n_repro", 3)),
                control_cache=control_cache, early_stop_repro=True)
            stamp(unit, fingerprint)
            ctx.units.append(unit)
            ctx.ledger.merge(unit.cost)
        ctx.candidates.clear()
        return ctx


@OPERATORS.register("minimize")
class Minimize(InterventionalOp):
    """ddmin-slice REPRODUCIBLE units to MINIMAL. Params: none."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.sdk.schemas import EvidenceTier
        from causal_data_juicer.slicing.ddmin import minimize_unit
        services = engine_services(ctx)
        eps = {e.id: e for e in ctx.episodes}
        for i, unit in enumerate(ctx.units):
            if unit.tier >= EvidenceTier.REPRODUCIBLE:
                ctx.units[i] = minimize_unit(services["replayer"], eps[unit.episode_id],
                                             ctx.snapshots, unit)
        return ctx


# ------------------------------- compile -----------------------------------

@OPERATORS.register("export_views")
class ExportViews(CompileOp):
    """Compile SFT / DPO / memory / regression views. Params: none."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.compiler.exports import compile_all
        ctx.exports.update({k: str(v) for k, v in
                            compile_all(ctx.units, ctx.episodes,
                                        ctx.workdir / "exports").items()})
        return ctx


@OPERATORS.register("export_trl")
class ExportTRL(CompileOp):
    """Trainer-native exports. Params: formats (default [trl-sft, trl-dpo, verl])."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.compiler.adapters import ADAPTERS
        for fmt in self.params.get("formats", ["trl-sft", "trl-dpo", "verl"]):
            suffix = "" if fmt == "verl" else ".jsonl"
            path = ADAPTERS[fmt](ctx.units, ctx.episodes,
                                 ctx.workdir / "exports" / f"{fmt}{suffix}")
            ctx.exports[fmt] = str(path)
        return ctx


@OPERATORS.register("save_run")
class SaveRun(CompileOp):
    """Persist the context as a run directory (episodes/snapshots/units).
    Params: none (uses the recipe workdir)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.run_store import RunStore
        from causal_data_juicer.sdk.schemas import EvidenceTier
        validated = [u for u in ctx.units
                     if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED]
        report = {"recipe": ctx.meta.get("recipe", ""),
                  "episodes": len(ctx.episodes), "units": len(ctx.units),
                  "validated_units": len(validated),
                  "cost": ctx.ledger.model_dump(), "exports": ctx.exports}
        RunStore(ctx.workdir).save(ctx.episodes, ctx.snapshots, ctx.units, report)
        return ctx
