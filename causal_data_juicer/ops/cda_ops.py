"""Identify -> Generate -> Filter -> Validate: the CDA mainline, with the
execution gate kept intact.

The counterfactual-data-augmentation literature converged on a four-stage
shape: find the causal terms, intervene on them, filter what came back,
then trust it. Most systems stop at "filter", and a model's own judgement
becomes the evidence. Here the fourth stage is a *real paired replay*, so
generation and constraint-filtering earn their own rung —
``CONSTRAINT_VALIDATED`` — and nothing more. Promotion past it is bought
with execution, never with fluency.

    intervention_site_mapper      identify: what can be intervened on
    do_counterfactual_mapper      generate: do(Z_j = z_j'), descendants only
    counterfactual_validity_filter  filter: composable hard/soft verdicts
    replay_promotion_selector     validate: spend the replay budget where
                                  it buys the most new information
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from causal_data_juicer.ops.base_op import (
    OPERATORS,
    ObservationalOp,
    OpContext,
    SourceOp,
)
from causal_data_juicer.sdk.schemas import (
    EvidenceTier,
    GeneratedBranch,
    GenerationProvenance,
    Intervention,
    InterventionSite,
    InterventionType,
    ReplayRequest,
    SiteKind,
    ToolCall,
    ValidationVector,
    digest_of,
)

# Descendants of a step, in the order the engine can actually re-derive them.
DEFAULT_DESCENDANTS = ["tool_output", "next_action", "outcome"]

_TRIPLE = re.compile(r"^\s*([\w./-]+)\s+(is|has|uses|requires|returns|imports)\s+(.+?)\s*$")


# =============================== identify ===================================


@OPERATORS.register("intervention_site_mapper")
class InterventionSiteMapper(ObservationalOp):
    """Identify the variables in a trajectory that a ``do`` could act on,
    typed and annotated with what must stay fixed.

    Sites are read off recorded steps: tool arguments (``ToolArgument``),
    structured fields inside written artifacts (``StructuredField``),
    reasoning sentences (``Rationale``), retrieved blocks (``TextSpan``),
    subject-predicate-object statements (``SemanticTriple``), and the
    actions themselves (``AgentAction``). ``influence_score`` is an
    openly heuristic prior for ordering work — it is never evidence.

    Params: kinds (list, default all), rationale_paths (default
    ['thoughts.md']), context_paths (default ['context.md']),
    invariants (default ['task', 'repository', 'user_intent'])."""

    def run(self, ctx: OpContext) -> OpContext:
        kinds = set(self.params.get("kinds", [k.value for k in SiteKind]))
        rationale_paths = set(self.params.get("rationale_paths", ["thoughts.md"]))
        context_paths = set(self.params.get("context_paths", ["context.md"]))
        invariants = list(self.params.get("invariants", ["task", "repository", "user_intent"]))
        sites: list[InterventionSite] = []

        for ep in ctx.episodes:
            n_steps = max(1, len(ep.steps))
            for step in ep.steps:
                action = step.action
                # later steps sit closer to the outcome: a crude, stated prior
                position = (step.index + 1) / n_steps
                path = str(action.args.get("path", ""))

                if SiteKind.AGENT_ACTION.value in kinds:
                    sites.append(
                        InterventionSite(
                            episode_id=ep.id,
                            step_index=step.index,
                            kind=SiteKind.AGENT_ACTION,
                            variable=f"action.step_{step.index}.tool",
                            current_value=action.tool,
                            influence_score=round(0.5 * position, 3),
                            invariants=invariants,
                            possible_descendants=list(DEFAULT_DESCENDANTS),
                            locator={"step": step.index},
                        )
                    )

                if SiteKind.TOOL_ARGUMENT.value in kinds:
                    for arg, value in action.args.items():
                        if not isinstance(value, str) or "\n" in value:
                            continue  # multi-line payloads are handled below
                        sites.append(
                            InterventionSite(
                                episode_id=ep.id,
                                step_index=step.index,
                                kind=SiteKind.TOOL_ARGUMENT,
                                variable=f"tool_argument.{arg}",
                                current_value=value,
                                influence_score=round(0.7 * position, 3),
                                invariants=invariants,
                                possible_descendants=list(DEFAULT_DESCENDANTS),
                                locator={"step": step.index, "arg": arg},
                            )
                        )

                content = action.args.get("content")
                if not isinstance(content, str):
                    continue
                lines = content.splitlines()

                if SiteKind.STRUCTURED_FIELD.value in kinds:
                    for i, line in enumerate(lines):
                        m = re.match(r"^\s*([\w.-]+)\s*[:=]\s*(.+?)\s*$", line)
                        if m:
                            sites.append(
                                InterventionSite(
                                    episode_id=ep.id,
                                    step_index=step.index,
                                    kind=SiteKind.STRUCTURED_FIELD,
                                    variable=f"field.{m.group(1)}",
                                    current_value=m.group(2),
                                    influence_score=round(0.8 * position, 3),
                                    invariants=invariants,
                                    possible_descendants=list(DEFAULT_DESCENDANTS),
                                    locator={"step": step.index, "path": path, "line": i},
                                )
                            )

                if SiteKind.SEMANTIC_TRIPLE.value in kinds:
                    for i, line in enumerate(lines):
                        m = _TRIPLE.match(line)
                        if m:
                            sites.append(
                                InterventionSite(
                                    episode_id=ep.id,
                                    step_index=step.index,
                                    kind=SiteKind.SEMANTIC_TRIPLE,
                                    variable=f"triple.{m.group(1)}.{m.group(2)}",
                                    current_value=m.group(3),
                                    influence_score=round(0.6 * position, 3),
                                    invariants=invariants,
                                    possible_descendants=list(DEFAULT_DESCENDANTS),
                                    locator={"step": step.index, "path": path, "line": i},
                                )
                            )

                if SiteKind.RATIONALE.value in kinds and path in rationale_paths:
                    for i, line in enumerate(lines):
                        if line.strip():
                            sites.append(
                                InterventionSite(
                                    episode_id=ep.id,
                                    step_index=step.index,
                                    kind=SiteKind.RATIONALE,
                                    variable=f"rationale.sentence_{i}",
                                    current_value=line.strip(),
                                    # earlier reasoning carries more weight
                                    influence_score=round(0.9 * (1 - i / max(1, len(lines))), 3),
                                    invariants=invariants,
                                    possible_descendants=list(DEFAULT_DESCENDANTS),
                                    locator={"step": step.index, "path": path, "line": i},
                                )
                            )

                if SiteKind.TEXT_SPAN.value in kinds and path in context_paths:
                    for i, block in enumerate(content.split("\n\n")):
                        if block.strip():
                            sites.append(
                                InterventionSite(
                                    episode_id=ep.id,
                                    step_index=step.index,
                                    kind=SiteKind.TEXT_SPAN,
                                    variable=f"context.block_{i}",
                                    current_value=block.strip()[:200],
                                    influence_score=round(0.5 * position, 3),
                                    invariants=invariants,
                                    possible_descendants=list(DEFAULT_DESCENDANTS),
                                    locator={"step": step.index, "path": path, "block": i},
                                )
                            )

        ctx.meta["sites"] = [s.model_dump(mode="json") for s in sites]
        ctx.services["sites"] = sites
        return ctx


# =============================== generate ===================================


def _edit_line(content: str, line: int, text: str) -> str:
    lines = content.splitlines()
    if 0 <= line < len(lines):
        lines[line] = text
    return "\n".join(lines)


def _drop_block(content: str, block: int) -> str:
    blocks = [b for b in content.split("\n\n") if b.strip()]
    if 0 <= block < len(blocks):
        blocks.pop(block)
    return "\n\n".join(blocks)


class _NullLLM:
    """Stand-in so `descendant_regeneration` degrades to a *declared*
    no-model behaviour instead of silently pretending to have generated."""

    model = "none"

    def complete(self, messages):  # pragma: no cover - never called
        raise RuntimeError("descendant_regeneration needs base_url/model")


@OPERATORS.register("do_counterfactual_mapper")
class DoCounterfactualMapper(SourceOp):
    """``do(Z_j = z_j')`` on identified sites, regenerating **only the
    declared descendants**.

    This is the difference between a counterfactual and a rewrite: the site
    says what changes and what must hold, so the edit touches one variable
    and the engine re-derives the downstream consequences by *executing*
    them. Unconstrained "rewrite the sample" prompting cannot make that
    distinction, which is why it is not offered here.

    Strategies (``strategy`` may be a list):
      mask_edit               blank the site's value (the null intervention)
      retrieve_edit           substitute a value from ``values`` / ``values_file``
      rationale_edit          truncate the reasoning at this sentence
      semantic_triple_edit    swap the object of a subject-predicate-object
      descendant_regeneration ask a model for the new value, constrained to
                              the site and its invariants (needs base_url/model)

    Every branch records its do(), the invariants it promises to preserve,
    and full generation provenance. Branches enter at SUGGESTED; the filter
    can raise them to CONSTRAINT_VALIDATED; only a paired replay goes higher.

    Params: strategy (default ['mask_edit']), values (list) or values_file,
    kinds (restrict site kinds), max_sites (default 0 = all),
    target_outcome (default 'success'), base_url, model, seed."""

    def run(self, ctx: OpContext) -> OpContext:
        sites: list[InterventionSite] = list(ctx.services.get("sites", []))
        if not sites:
            raise ValueError(
                "do_counterfactual_mapper needs sites — run intervention_site_mapper first"
            )
        strategies = self.params.get("strategy", ["mask_edit"])
        if isinstance(strategies, str):
            strategies = [strategies]
        kinds = set(self.params.get("kinds", [])) or None
        values = list(self.params.get("values", []))
        if self.params.get("values_file"):
            values += json.loads(Path(str(self.params["values_file"])).read_text())
        max_sites = int(self.params.get("max_sites", 0))
        target = str(self.params.get("target_outcome", "success"))
        seed = self.params.get("seed")
        eps = {e.id: e for e in ctx.episodes}

        llm = None
        if "descendant_regeneration" in strategies:
            from causal_data_juicer.runtime.llm import DiskCachedLLM, OpenAICompatClient

            if not self.params.get("base_url"):
                raise ValueError("descendant_regeneration needs base_url and model")
            llm = DiskCachedLLM(
                OpenAICompatClient(self.params["base_url"], self.params["model"]),
                ctx.workdir / "llm_cache",
            )

        ordered = sorted(sites, key=lambda s: -s.influence_score)
        if kinds:
            ordered = [s for s in ordered if s.kind.value in kinds]
        if max_sites:
            ordered = ordered[:max_sites]

        branches: list[GeneratedBranch] = []
        for site in ordered:
            ep = eps.get(site.episode_id)
            if ep is None:
                continue
            step = next((s for s in ep.steps if s.index == site.step_index), None)
            if step is None:
                continue
            for strategy in strategies:
                new_value, descendants = self._apply(strategy, site, values, llm)
                if new_value is None:
                    continue
                iv = self._intervention(site, step, new_value, strategy)
                if iv is None:
                    continue
                branches.append(
                    GeneratedBranch(
                        episode_id=ep.id,
                        task_id=ep.task_id,
                        site_id=site.id,
                        site=site,
                        intervention=iv,
                        target_outcome=target,
                        invariants=list(site.invariants),
                        provenance=GenerationProvenance(
                            generator="do_counterfactual_mapper",
                            strategy=strategy,
                            model=(
                                getattr(llm, "model", None)
                                if strategy == "descendant_regeneration"
                                else None
                            ),
                            prompt_digest=(
                                digest_of({"site": site.variable, "strategy": strategy})
                                if strategy == "descendant_regeneration"
                                else None
                            ),
                            seed=None if seed is None else int(seed),
                            regenerated_descendants=descendants,
                        ),
                        tier=EvidenceTier.SUGGESTED,
                    )
                )
        ctx.services.setdefault("branches", []).extend(branches)
        ctx.meta["do_counterfactual_mapper"] = {
            "sites_considered": len(ordered),
            "branches": len(branches),
            "strategies": list(strategies),
        }
        return ctx

    # -- strategies ---------------------------------------------------------

    def _apply(self, strategy, site, values, llm):
        """Return (new value for the site, descendants we claim to re-derive)."""
        if strategy == "mask_edit":
            return "", list(site.possible_descendants)
        if strategy == "retrieve_edit":
            return (values[0] if values else None), list(site.possible_descendants)
        if strategy == "rationale_edit":
            return ("" if site.kind == SiteKind.RATIONALE else None), list(
                site.possible_descendants
            )
        if strategy == "semantic_triple_edit":
            if site.kind != SiteKind.SEMANTIC_TRIPLE:
                return None, []
            return (values[0] if values else "unspecified"), list(site.possible_descendants)
        if strategy == "descendant_regeneration":
            prompt = (
                "Rewrite ONLY this value, changing nothing else. Keep these "
                f"invariant: {', '.join(site.invariants)}.\n"
                f"Variable: {site.variable}\nCurrent value: {site.current_value}\n"
                "Reply with the new value and nothing else."
            )
            resp = llm.complete([{"role": "user", "content": prompt}])
            return resp.text.strip().splitlines()[0] if resp.text.strip() else None, list(
                site.possible_descendants
            )
        return None, []

    def _intervention(self, site, step, new_value, strategy):
        """Turn a site + new value into an executable intervention."""
        action = step.action
        loc = site.locator
        if site.kind == SiteKind.TOOL_ARGUMENT and "arg" in loc:
            args = {**action.args, loc["arg"]: new_value}
            new_action = ToolCall(tool=action.tool, args=args)
        elif (
            site.kind
            in (
                SiteKind.STRUCTURED_FIELD,
                SiteKind.SEMANTIC_TRIPLE,
                SiteKind.RATIONALE,
            )
            and "line" in loc
        ):
            content = action.args.get("content", "")
            if site.kind == SiteKind.RATIONALE and strategy == "rationale_edit":
                kept = content.splitlines()[: loc["line"]]
                updated = "\n".join(kept)
            elif site.kind == SiteKind.SEMANTIC_TRIPLE:
                original = content.splitlines()[loc["line"]]
                updated = _edit_line(
                    content, loc["line"], original.rsplit(" ", 1)[0] + f" {new_value}"
                )
            else:
                original = content.splitlines()[loc["line"]]
                key = original.split(":", 1)[0] if ":" in original else original.split("=", 1)[0]
                sep = ":" if ":" in original else "="
                updated = _edit_line(content, loc["line"], f"{key}{sep} {new_value}")
            new_action = ToolCall(tool=action.tool, args={**action.args, "content": updated})
        elif site.kind == SiteKind.TEXT_SPAN and "block" in loc:
            updated = _drop_block(action.args.get("content", ""), loc["block"])
            new_action = ToolCall(tool=action.tool, args={**action.args, "content": updated})
        elif site.kind == SiteKind.AGENT_ACTION:
            if "path" not in action.args:
                return None
            new_action = ToolCall(tool="read_file", args={"path": action.args["path"]})
        else:
            return None
        return Intervention(
            type=InterventionType.ACTION_REPLACE,
            target_step=site.step_index,
            new_action=new_action,
            rationale=f"do({site.variable} := {new_value!r}) via {strategy}",
            source=f"do:{strategy}:{site.variable}",
        )


# ================================ filter ====================================


@OPERATORS.register("counterfactual_validity_filter")
class CounterfactualValidityFilter(ObservationalOp):
    """Composable verdicts on generated branches — hard constraints gate,
    soft scores rank, and rejections keep their provenance.

    Hard (all must hold, checked in order):
      intervention_fidelity   the edit actually changed the named variable
      target_outcome_shift    the branch is *aimed* at flipping the outcome
      invariant_preservation  nothing outside the site moved
      schema_validity         the resulting action is well-formed and
                              executable by a registered tool

    Soft (recorded, never gating): minimality, semantic_proximity, fluency,
    diversity, verifier_confidence.

    Passing lifts a branch to **CONSTRAINT_VALIDATED and no further** — this
    operator never executes anything, so it cannot make a causal claim. A
    rejected branch is kept with ``failed_at`` and a reason, because the
    rejections are the training signal for the generator.

    Params: keep_rejected (default true), min_proximity (default 0.0,
    soft-only), drop_identical (default true)."""

    def run(self, ctx: OpContext) -> OpContext:
        branches: list[GeneratedBranch] = list(ctx.services.get("branches", []))
        if not branches:
            ctx.meta["counterfactual_validity_filter"] = {"branches": 0}
            return ctx
        keep_rejected = bool(self.params.get("keep_rejected", True))
        drop_identical = bool(self.params.get("drop_identical", True))
        eps = {e.id: e for e in ctx.episodes}
        registry = ctx.services.get("tool_registry")
        tools: set[str] = (
            set(registry.tools)
            if registry is not None
            else {"write_file", "read_file", "run_pytest", "run_check", "send_report"}
        )

        accepted: list[GeneratedBranch] = []
        rejected: list[GeneratedBranch] = []
        seen: set[str] = set()
        for br in branches:
            ep = eps.get(br.episode_id)
            step = (
                next((s for s in ep.steps if s.index == br.intervention.target_step), None)
                if ep
                else None
            )
            v = self._judge(br, step, tools, drop_identical, seen)
            br.validation = v
            if v.accepted:
                br.tier = EvidenceTier.CONSTRAINT_VALIDATED  # ceiling: no execution happened
                accepted.append(br)
                seen.add(br.effect_signature())
            else:
                rejected.append(br)

        ctx.services["branches"] = accepted
        if keep_rejected:
            ctx.services.setdefault("rejected_branches", []).extend(rejected)
        ctx.meta["counterfactual_validity_filter"] = {
            "accepted": len(accepted),
            "rejected": len(rejected),
            "rejected_at": _count_by(
                r.validation.failed_at for r in rejected if r.validation is not None
            ),
        }
        return ctx

    def _judge(self, br, step, tools, drop_identical, seen) -> ValidationVector:
        v = ValidationVector()
        new_action = br.intervention.new_action
        site = br.site

        # schema / executable validity
        v.schema_validity = bool(
            new_action is not None
            and new_action.tool in tools
            and isinstance(new_action.args, dict)
        )

        # intervention fidelity: did the named variable actually move?
        original = step.action if step is not None else None
        if original is None or new_action is None:
            v.intervention_fidelity = False
        else:
            v.intervention_fidelity = new_action.model_dump() != original.model_dump()

        # target outcome shift: a do() aimed at nothing is not a counterfactual
        v.target_outcome_shift = bool(br.target_outcome)

        # invariant preservation: only the site's own locus may differ
        v.invariant_preservation = self._invariants_hold(br, original, new_action, site)

        # soft scores
        if original is not None and new_action is not None:
            a, b = (
                json.dumps(original.args, sort_keys=True),
                json.dumps(new_action.args, sort_keys=True),
            )
            v.semantic_proximity = round(_similarity(a, b), 3)
            v.minimality = round(1.0 - min(1.0, abs(len(b) - len(a)) / max(1, len(a))), 3)
            v.fluency = 1.0 if (new_action.args.get("content", "x") or "x").strip() else 0.0
        sig = br.effect_signature()
        v.diversity = 0.0 if sig in seen else 1.0
        v.verifier_confidence = None  # only a replay can fill this in

        failed = v.first_failure()
        if failed is None and drop_identical and v.diversity == 0.0:
            failed, reason = "diversity", "an identical effect signature was already accepted"
        else:
            reason = {
                "intervention_fidelity": "the edit did not change the action",
                "target_outcome_shift": "no target outcome was declared",
                "invariant_preservation": "something outside the intervention site changed",
                "schema_validity": "the resulting action is not executable by a registered tool",
            }.get(failed or "", "")
        v.accepted = failed is None
        v.failed_at = failed
        v.reason = reason
        return v

    @staticmethod
    def _invariants_hold(br, original, new_action, site) -> bool:
        if original is None or new_action is None:
            return False
        if original.tool != new_action.tool and (
            site is None or site.kind != SiteKind.AGENT_ACTION
        ):
            return False  # swapping the tool is not "one variable moved"
        touched = set(original.args) ^ set(new_action.args)
        if touched:
            return False  # no argument may appear or vanish
        changed = [k for k in original.args if original.args[k] != new_action.args.get(k)]
        if site is not None and site.kind == SiteKind.TOOL_ARGUMENT:
            return changed == [site.locator.get("arg")]
        # content edits: the path (identity of the artifact) must not move
        if "path" in original.args and original.args["path"] != new_action.args.get("path"):
            return False
        return len(changed) <= 1


def _count_by(values) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for v in values:
        out[str(v)] += 1
    return dict(out)


def _similarity(a: str, b: str) -> float:
    """Character-trigram Jaccard — cheap, deterministic, no model."""

    def grams(s: str) -> set[str]:
        return {s[i : i + 3] for i in range(max(1, len(s) - 2))}

    ga, gb = grams(a), grams(b)
    return len(ga & gb) / max(1, len(ga | gb))


# =============================== validate ===================================


@OPERATORS.register("replay_promotion_selector")
class ReplayPromotionSelector(ObservationalOp):
    """Decide which generated branches are worth real execution.

    Generation is cheap and unreliable; replay is expensive and decisive, so
    the budget should buy *information*, not volume. Branches are clustered
    by effect signature — two edits that change the same variable the same
    way are one experiment — and each cluster is scored

        value_i = P(flip)_i x novelty_i x coverage_i x uncertainty_i / cost_i

    then packed greedily by value density under ``budget``. A cluster's
    representative is queued first; ``sequential`` mode then re-scores the
    remaining clusters using the flip rate observed so far (a Beta-Bernoulli
    posterior over the cluster's strategy), and stops early once every
    remaining cluster falls below ``min_value`` — the branches that never
    reach a replay are recorded, not silently dropped.

    The output is a list of ReplayRequests in ctx.services['replay_requests']
    and, for the interventional operators downstream, ctx.candidates.

    Params: budget (replays, default 20), sequential (default true),
    min_value (default 0.01), cost_per_replay (default 1.0),
    prior_flip (default 0.3)."""

    def run(self, ctx: OpContext) -> OpContext:
        branches: list[GeneratedBranch] = list(ctx.services.get("branches", []))
        budget = float(self.params.get("budget", 20))
        cost = float(self.params.get("cost_per_replay", 1.0))
        min_value = float(self.params.get("min_value", 0.01))
        sequential = bool(self.params.get("sequential", True))
        prior = float(self.params.get("prior_flip", 0.3))
        if not branches:
            ctx.meta["replay_promotion_selector"] = {"requested": 0, "clusters": 0}
            return ctx

        clusters: dict[str, list[GeneratedBranch]] = defaultdict(list)
        for br in branches:
            clusters[br.effect_signature()].append(br)

        # coverage: how many *episodes* a cluster is the only witness for
        eps_per_cluster = {k: {b.episode_id for b in v} for k, v in clusters.items()}
        episode_counts: dict[str, int] = defaultdict(int)
        for eps in eps_per_cluster.values():
            for e in eps:
                episode_counts[e] += 1

        # Beta-Bernoulli posterior per strategy, seeded from the stated prior
        alpha: dict[str, float] = defaultdict(lambda: prior * 2)
        beta: dict[str, float] = defaultdict(lambda: (1 - prior) * 2)
        observed = ctx.services.get("strategy_outcomes", {})
        for strategy, (flips, tries) in observed.items():
            alpha[strategy] += flips
            beta[strategy] += max(0, tries - flips)

        spent = 0.0
        requests: list[ReplayRequest] = []
        skipped: list[dict] = []
        pending = list(clusters.items())
        while pending:
            scored = []
            for sig, members in pending:
                rep = max(members, key=lambda b: b.site.influence_score if b.site else 0.0)
                strategy = rep.provenance.strategy or "unknown"
                p_flip = alpha[strategy] / (alpha[strategy] + beta[strategy])
                novelty = 1.0 / len(members)  # a big cluster is mostly duplicates
                coverage = sum(1.0 / episode_counts[e] for e in eps_per_cluster[sig]) / len(
                    eps_per_cluster[sig]
                )
                # uncertainty peaks at p=0.5: that is where a replay teaches most
                uncertainty = 4 * p_flip * (1 - p_flip)
                value = p_flip * novelty * coverage * max(uncertainty, 1e-3) / max(cost, 1e-9)
                scored.append((value, sig, rep, members, p_flip))
            scored.sort(key=lambda t: -t[0])
            value, sig, rep, members, p_flip = scored[0]
            if spent + cost > budget or value < min_value:
                skipped.extend(
                    {"signature": s, "value": round(v, 5), "branches": len(m)}
                    for v, s, _r, m, _p in scored
                )
                break
            requests.append(
                ReplayRequest(
                    branch_id=rep.id,
                    episode_id=rep.episode_id,
                    effect_signature=sig,
                    priority=round(value, 5),
                    estimated_cost=cost,
                    is_cluster_representative=True,
                    rationale=(
                        f"cluster of {len(members)} via {rep.provenance.strategy}; "
                        f"P(flip)~{p_flip:.2f}"
                    ),
                )
            )
            spent += cost
            pending = [(s, m) for s, m in pending if s != sig]
            if not sequential:
                # static packing: keep the initial ordering, no posterior update
                for value2, sig2, rep2, _members2, p2 in scored[1:]:
                    if spent + cost > budget or value2 < min_value:
                        skipped.extend(
                            {"signature": s3, "value": round(v3, 5), "branches": len(m3)}
                            for v3, s3, _r3, m3, _p3 in scored[1:]
                        )
                        pending = []
                        break
                    requests.append(
                        ReplayRequest(
                            branch_id=rep2.id,
                            episode_id=rep2.episode_id,
                            effect_signature=sig2,
                            priority=round(value2, 5),
                            estimated_cost=cost,
                            is_cluster_representative=True,
                            rationale=f"static pack; P(flip)~{p2:.2f}",
                        )
                    )
                    spent += cost
                    pending = [(s, m) for s, m in pending if s != sig2]
                break

        by_id = {b.id: b for b in branches}
        ctx.services["replay_requests"] = requests
        ctx.candidates.extend(
            (ep, by_id[r.branch_id].intervention)
            for r in requests
            for ep in ctx.episodes
            if ep.id == r.episode_id
        )
        ctx.meta["replay_promotion_selector"] = {
            "clusters": len(clusters),
            "requested": len(requests),
            "budget": budget,
            "spent": spent,
            "skipped": skipped[:20],
            "skipped_total": len(skipped),
        }
        return ctx


@OPERATORS.register("attach_generation_provenance")
class AttachGenerationProvenance(ObservationalOp):
    """Reconnect executed units to the branches that proposed them.

    Without this the ladder has a hole: the selector hands the engine bare
    interventions, so a finished corpus cannot say which rows came from a
    model, which constraints they cleared beforehand, or which site was
    intervened on. Each matching unit gets ``provenance['generation']``,
    ``provenance['constraint_validation']`` and ``provenance['site']``.

    Units whose execution did not flip keep their execution-derived tier —
    passing a constraint filter is not evidence, and this operator never
    raises a tier. Params: none."""

    def run(self, ctx: OpContext) -> OpContext:
        branches = list(ctx.services.get("branches", []))
        by_iv = {b.intervention.id: b for b in branches}
        attached = 0
        for unit in ctx.units:
            br = by_iv.get(unit.intervention.id)
            if br is None:
                continue
            unit.provenance["generation"] = br.provenance.model_dump(mode="json")
            unit.provenance["site"] = (
                br.site.model_dump(mode="json") if br.site else {"id": br.site_id}
            )
            if br.validation is not None:
                unit.provenance["constraint_validation"] = br.validation.model_dump(mode="json")
            unit.provenance["generated_tier_before_execution"] = br.tier.name
            attached += 1
        ctx.meta["attach_generation_provenance"] = {
            "attached": attached,
            "units": len(ctx.units),
            "promoted_by_execution": sum(
                1 for u in ctx.units if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED
            ),
        }
        return ctx


@OPERATORS.register("effect_signature_deduplicator")
class EffectSignatureDeduplicator(ObservationalOp):
    """Collapse generated branches that would run the same experiment.

    Two edits that change the same variable at the same step to the same
    value are one counterfactual, however differently they were phrased.
    Deduplicating *before* the selector means the replay budget is spent on
    distinct hypotheses rather than on paraphrases; the survivors keep a
    ``duplicates`` count so the corpus still records how often a strategy
    proposed the same thing.

    Keeps the representative with the highest site influence_score.
    Params: none."""

    def run(self, ctx: OpContext) -> OpContext:
        branches: list[GeneratedBranch] = list(ctx.services.get("branches", []))
        groups: dict[str, list[GeneratedBranch]] = defaultdict(list)
        for br in branches:
            groups[br.effect_signature()].append(br)
        kept: list[GeneratedBranch] = []
        for members in groups.values():
            rep = max(members, key=lambda b: b.site.influence_score if b.site else 0.0)
            if len(members) > 1:
                rep.provenance.regenerated_descendants = list(
                    rep.provenance.regenerated_descendants
                )
                ctx.meta.setdefault("duplicate_signatures", []).append(
                    {
                        "signature": rep.effect_signature(),
                        "duplicates": len(members) - 1,
                        "strategies": sorted({m.provenance.strategy for m in members}),
                    }
                )
            kept.append(rep)
        ctx.services["branches"] = kept
        ctx.meta["effect_signature_deduplicator"] = {
            "before": len(branches),
            "after": len(kept),
            "collapsed": len(branches) - len(kept),
        }
        return ctx
