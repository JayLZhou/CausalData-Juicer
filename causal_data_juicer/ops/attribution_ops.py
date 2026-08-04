"""Attribution operators — the published-strategy family, as a vocabulary.

Nine case studies each hand-built the same shape: pick a step, propose a
counterfactual variant of *something inside it* (a retrieved document, a
teammate's message, a reasoning sentence, an SQL clause), let the engine
execute both branches, and read the difference as credit. Those scripts
now exist as composable operators, so a recipe can say `context_ablate`
where it used to require a bespoke file.

Every proposal here is **deterministic** — leave-one-out, replace-from-table,
truncate-at-sentence — so recipes using them are reproducible without any
model. The execution (and therefore the evidence tier) still comes from the
interventional operators downstream.
"""

from __future__ import annotations

import json
from pathlib import Path

from causal_data_juicer.ops.base_op import (
    OPERATORS,
    CompileOp,
    ObservationalOp,
    OpContext,
    SourceOp,
)


def _steps_writing(episode, path: str):
    """Yield (index, step) for steps that write ``path`` — the assembly point
    an ablation intervenes on."""
    for step in episode.steps:
        action = step.action
        if action.tool == "write_file" and action.args.get("path") == path:
            yield step.index, step


def _replace_write(step_index: int, path: str, content: str, source: str, rationale: str):
    from causal_data_juicer.sdk.schemas import Intervention, InterventionType, ToolCall

    return Intervention(
        type=InterventionType.ACTION_REPLACE,
        target_step=step_index,
        new_action=ToolCall(tool="write_file", args={"path": path, "content": content}),
        rationale=rationale,
        source=source,
    )


# ------------------------------- sources -----------------------------------


@OPERATORS.register("context_ablate")
class ContextAblate(SourceOp):
    """Leave-one-document-out over an assembled context (ContextCite
    semantics): each candidate drops exactly one block, so a downstream
    reader that still succeeds proves the block was not load-bearing.

    Params: path (default context.md), separator (default '\\n\\n'),
    keep_min (default 1)."""

    def run(self, ctx: OpContext) -> OpContext:
        path = str(self.params.get("path", "context.md"))
        sep = str(self.params.get("separator", "\n\n"))
        keep_min = int(self.params.get("keep_min", 1))
        for ep in ctx.episodes:
            for idx, step in _steps_writing(ep, path):
                blocks = [b for b in step.action.args["content"].split(sep) if b.strip()]
                if len(blocks) <= keep_min:
                    continue
                for i, block in enumerate(blocks):
                    reduced = sep.join(blocks[:i] + blocks[i + 1 :])
                    label = block.strip().splitlines()[0][:40]
                    ctx.candidates.append(
                        (
                            ep,
                            _replace_write(
                                idx,
                                path,
                                reduced,
                                f"ablate:{label}",
                                f"drop context block {i}: {label}",
                            ),
                        )
                    )
        return ctx


@OPERATORS.register("message_ablate")
class MessageAblate(SourceOp):
    """Multi-agent message credit: replace one teammate's message with a
    supplied alternative and let downstream agents re-react (needs
    `continuation_policy` at replay time to be meaningful).

    Params: path (default inbox.md), replacements (list of strings, or a
    JSON file via replacements_file)."""

    def run(self, ctx: OpContext) -> OpContext:
        path = str(self.params.get("path", "inbox.md"))
        replacements = list(self.params.get("replacements", []))
        if self.params.get("replacements_file"):
            replacements += json.loads(Path(str(self.params["replacements_file"])).read_text())
        if not replacements:
            raise ValueError("message_ablate needs `replacements` or `replacements_file`")
        for ep in ctx.episodes:
            for idx, _step in _steps_writing(ep, path):
                for j, text in enumerate(replacements):
                    ctx.candidates.append(
                        (
                            ep,
                            _replace_write(
                                idx,
                                path,
                                str(text),
                                f"message:{j}",
                                f"replace the message at step {idx} with variant {j}",
                            ),
                        )
                    )
        return ctx


@OPERATORS.register("thought_truncate")
class ThoughtTruncate(SourceOp):
    """Thought-anchor probing without a model: truncate a reasoning trace at
    each sentence boundary, so the earliest truncation that still flips
    marks the sentence carrying the counterfactual weight.

    Params: path (default thoughts.md)."""

    def run(self, ctx: OpContext) -> OpContext:
        path = str(self.params.get("path", "thoughts.md"))
        for ep in ctx.episodes:
            for idx, step in _steps_writing(ep, path):
                lines = [ln for ln in step.action.args["content"].splitlines() if ln.strip()]
                for k in range(1, len(lines)):
                    ctx.candidates.append(
                        (
                            ep,
                            _replace_write(
                                idx,
                                path,
                                "\n".join(lines[:k]),
                                f"truncate:{k}",
                                f"keep only the first {k} of {len(lines)} thoughts",
                            ),
                        )
                    )
        return ctx


@OPERATORS.register("clause_perturb")
class ClausePerturb(SourceOp):
    """Clause-level stress perturbations (CAPER semantics): patch one line of
    a written artifact with a supplied variant, so the verifier decides
    which clauses are critical and which are harmless.

    Params: path (required), patches (list of {line, text})."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.sdk.schemas import (
            ArgEdit,
            Intervention,
            InterventionType,
            LinePatch,
        )

        path = str(self.params["path"])
        patches = list(self.params.get("patches", []))
        if not patches:
            raise ValueError("clause_perturb needs `patches` [{line, text}, …]")
        for ep in ctx.episodes:
            for idx, _step in _steps_writing(ep, path):
                for p in patches:
                    ctx.candidates.append(
                        (
                            ep,
                            Intervention(
                                type=InterventionType.TOOL_ARGUMENT_EDIT,
                                target_step=idx,
                                edits=[
                                    ArgEdit(
                                        arg="content",
                                        op="patch_lines",
                                        patches=[
                                            LinePatch(line=int(p["line"]), text=str(p["text"]))
                                        ],
                                    )
                                ],
                                rationale=f"perturb line {p['line']}",
                                source=f"clause:{p['line']}",
                            ),
                        )
                    )
        return ctx


# ---------------------------- observational --------------------------------


@OPERATORS.register("her_relabel")
class HerRelabel(ObservationalOp):
    """Hindsight relabelling: a failed trajectory is optimal supervision for
    the goal it *did* reach. Pure re-reading of recorded episodes, so the
    rows carry the OBSERVED ceiling. Params: out (default
    exports/her_sft.jsonl)."""

    def run(self, ctx: OpContext) -> OpContext:
        from causal_data_juicer.compiler.common import render_action

        out = Path(ctx.workdir) / str(self.params.get("out", "exports/her_sft.jsonl"))
        out.parent.mkdir(parents=True, exist_ok=True)
        rows: list[dict] = []
        for ep in ctx.episodes:
            if not ep.steps or (ep.outcome and ep.outcome.success):
                continue
            achieved = ep.steps[-1].observation.strip().splitlines()
            goal = achieved[-1][:160] if achieved else "the state reached at the end"
            rows.extend(
                {
                    "task_id": ep.task_id,
                    "prompt": f"[goal: {goal}]\n{ep.task_description}",
                    "completion": render_action(step.action),
                    "evidence_tier": "OBSERVED",
                }
                for step in ep.steps
            )
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        ctx.exports["her_sft"] = str(out)
        ctx.meta["her_relabel"] = {"rows": len(rows)}
        return ctx


# ------------------------------- compile -----------------------------------


@OPERATORS.register("credit_ate")
class CreditATE(CompileOp):
    """Compile step-level counterfactual credit — ATE = P(success | do(a'))
    - P(success | a) — straight from stored paired outcomes. Offline: no
    replay, no model. Params: out (default exports/credit_ate.jsonl)."""

    def run(self, ctx: OpContext) -> OpContext:
        from collections import defaultdict

        out = Path(ctx.workdir) / str(self.params.get("out", "exports/credit_ate.jsonl"))
        out.parent.mkdir(parents=True, exist_ok=True)
        by_step: dict[tuple[str, int], list] = defaultdict(list)
        for u in ctx.units:
            if u.intervened_outcome is None:
                continue
            by_step[(u.episode_id, u.effective_intervention().target_step)].append(u)
        rows = []
        for (episode_id, step), units in sorted(by_step.items()):
            baseline = float(any(u.original_outcome.success for u in units))
            treated = sum(float(u.intervened_outcome.success) for u in units) / len(units)
            rows.append(
                {
                    "episode_id": episode_id,
                    "task_id": units[0].task_id,
                    "step": step,
                    "n_interventions": len(units),
                    "p_success_intervened": round(treated, 3),
                    "p_success_original": round(baseline, 3),
                    "ate": round(treated - baseline, 3),
                    "evidence_tier": min(u.tier for u in units).name,
                }
            )
        out.write_text("".join(json.dumps(r) + "\n" for r in rows))
        ctx.exports["credit_ate"] = str(out)
        ctx.meta["credit_ate"] = {"steps_scored": len(rows)}
        return ctx


@OPERATORS.register("process_rewards")
class ProcessRewards(CompileOp):
    """Compile a process-reward view: one row per intervened atom, labelled
    by whether it was necessary (critical) or not (harmless) — the
    clause-PRM / step-PRM shape. Params: out (default
    exports/process_rewards.jsonl)."""

    def run(self, ctx: OpContext) -> OpContext:
        out = Path(ctx.workdir) / str(self.params.get("out", "exports/process_rewards.jsonl"))
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for u in ctx.units:
            if u.intervened_outcome is None:
                continue
            iv = u.effective_intervention()
            rows.append(
                {
                    "task_id": u.task_id,
                    "episode_id": u.episode_id,
                    "step": iv.target_step,
                    "source": iv.source,
                    "rationale": iv.rationale,
                    "label": "critical" if u.flipped else "harmless",
                    "reward": 1.0 if u.flipped else 0.0,
                    "evidence_tier": u.tier_name,
                }
            )
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        ctx.exports["process_rewards"] = str(out)
        ctx.meta["process_rewards"] = {"rows": len(rows)}
        return ctx
