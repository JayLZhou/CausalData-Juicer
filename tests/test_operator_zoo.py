"""The zoo must be real: registered, documented truthfully, and runnable.

The docs check exists because `docs/operator-zoo.md` once advertised a
zoo of Python classes while only 11 operators were actually registered and
usable in a recipe — the advertise-more-than-you-ship failure mode.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import causal_data_juicer.ops  # noqa: F401  (registers everything)
from causal_data_juicer.ops.base_op import OPERATORS, OpContext
from causal_data_juicer.sdk.schemas import (
    CausalUnit,
    Episode,
    EvidenceTier,
    Intervention,
    InterventionType,
    Outcome,
    Step,
    ToolCall,
)

REPO = Path(__file__).resolve().parent.parent


def _episode(task_id="t1", *, writes=(), success=False, observation="") -> Episode:
    steps = [
        Step(
            index=i,
            action=ToolCall(tool="write_file", args={"path": p, "content": c}),
            observation=observation,
        )
        for i, (p, c) in enumerate(writes)
    ]
    return Episode(
        task_id=task_id,
        task_description=f"task {task_id}",
        steps=steps,
        outcome=Outcome(success=success, passed=1 if success else 0, failed=0 if success else 1),
    )


def _unit(ep, *, step=0, flipped=True, tier=EvidenceTier.MINIMAL, source="fixer") -> CausalUnit:
    return CausalUnit(
        episode_id=ep.id,
        task_id=ep.task_id,
        intervention=Intervention(
            type=InterventionType.ACTION_REPLACE,
            target_step=step,
            new_action=ToolCall(tool="write_file", args={"path": "a.py", "content": "fixed"}),
            source=source,
        ),
        original_outcome=Outcome(success=False, failed=1),
        intervened_outcome=Outcome(success=flipped, passed=1 if flipped else 0),
        flipped=flipped,
        tier=tier,
    )


# ------------------------------ the contract --------------------------------


def test_zoo_size_and_categories():
    items = OPERATORS.items()
    assert len(items) >= 25, "the audit target is 25-40 shipped causal operators"
    cats = {cls.category for _, cls in items}
    assert cats == {"observational", "source", "interventional", "compile"}


def test_every_operator_is_documented_and_instantiable():
    for name, cls in OPERATORS.items():
        assert (cls.__doc__ or "").strip(), f"{name} has no docstring"
        assert cls(**{}) is not None


def test_docs_match_the_registry_exactly():
    """docs/operator-zoo.md is generated; drift is a test failure, not a
    stale-docs footnote."""
    proc = subprocess.run(
        [sys.executable, "scripts/gen_zoo_docs.py", "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cdj_ops_lists_every_registered_operator():
    from causal_data_juicer.ops.recipe import list_ops

    text = list_ops()
    for name, _cls in OPERATORS.items():  # noqa: PERF102 - Registry, not a dict
        assert name in text


# ------------------------- analysis operators -------------------------------


def test_filter_units_by_tier_and_flip(tmp_path):
    ep = _episode()
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    ctx.units = [
        _unit(ep, tier=EvidenceTier.MINIMAL, flipped=True),
        _unit(ep, tier=EvidenceTier.SUGGESTED, flipped=False),
    ]
    OPERATORS.get("filter_units")(min_tier="REPRODUCIBLE").run(ctx)
    assert len(ctx.units) == 1 and ctx.units[0].tier == EvidenceTier.MINIMAL


def test_filter_units_by_task_prefix_and_source(tmp_path):
    a, b = _episode("pydantic_01"), _episode("numpy_02")
    ctx = OpContext(workdir=tmp_path, episodes=[a, b])
    ctx.units = [_unit(a, source="fixer"), _unit(b, source="resample")]
    OPERATORS.get("filter_units")(task_prefix="pydantic").run(ctx)
    assert [u.task_id for u in ctx.units] == ["pydantic_01"]


def test_dedupe_units_collapses_same_effect(tmp_path):
    ep = _episode()
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    ctx.units = [_unit(ep), _unit(ep), _unit(ep, step=1)]
    OPERATORS.get("dedupe_units")().run(ctx)
    assert len(ctx.units) == 2  # same (episode, step, effect) collapsed


def test_sample_units_is_deterministic(tmp_path):
    ep = _episode()
    units = [_unit(ep, step=i) for i in range(10)]

    def sample():
        ctx = OpContext(workdir=tmp_path, episodes=[ep])
        ctx.units = list(units)
        OPERATORS.get("sample_units")(n=3, seed=7).run(ctx)
        return [u.id for u in ctx.units]

    assert sample() == sample()
    assert len(sample()) == 3


def test_cost_report_and_coverage_report(tmp_path):
    ep_failed, ep_ok = _episode("t_fail"), _episode("t_ok", success=True)
    ctx = OpContext(workdir=tmp_path, episodes=[ep_failed, ep_ok])
    ctx.units = [_unit(ep_failed, tier=EvidenceTier.MINIMAL)]
    ctx.ledger.replay_runs = 12
    ctx.ledger.charge_tool(3.0)
    OPERATORS.get("cost_report")(out="cost.json").run(ctx)
    OPERATORS.get("coverage_report")(out="coverage.json").run(ctx)
    cost = json.loads((tmp_path / "cost.json").read_text())
    cov = json.loads((tmp_path / "coverage.json").read_text())
    assert cost["validated_units"] == 1 and cost["replays_per_validated_unit"] == 12.0
    assert cov["failed_tasks"] == 1 and cov["covered_tasks"] == 1 and cov["coverage"] == 1.0
    assert cov["units_by_tier"] == {"MINIMAL": 1}


# ----------------------- attribution operators ------------------------------


def test_context_ablate_proposes_leave_one_out(tmp_path):
    ep = _episode(writes=[("context.md", "doc A\n\ndoc B\n\ndoc C")])
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    OPERATORS.get("context_ablate")().run(ctx)
    assert len(ctx.candidates) == 3
    contents = [iv.new_action.args["content"] for _ep, iv in ctx.candidates]
    assert all(c.count("doc") == 2 for c in contents)  # exactly one dropped each
    assert {iv.source for _ep, iv in ctx.candidates} == {
        "ablate:doc A",
        "ablate:doc B",
        "ablate:doc C",
    }


def test_context_ablate_skips_single_block(tmp_path):
    ep = _episode(writes=[("context.md", "only one doc")])
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    OPERATORS.get("context_ablate")().run(ctx)
    assert ctx.candidates == []


def test_message_ablate_uses_replacements(tmp_path):
    ep = _episode(writes=[("inbox.md", "use approach X")])
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    OPERATORS.get("message_ablate")(replacements=["use approach Y", "no guidance"]).run(ctx)
    assert [iv.new_action.args["content"] for _e, iv in ctx.candidates] == [
        "use approach Y",
        "no guidance",
    ]


def test_message_ablate_requires_replacements(tmp_path):
    ctx = OpContext(workdir=tmp_path, episodes=[_episode(writes=[("inbox.md", "x")])])
    with pytest.raises(ValueError, match="replacements"):
        OPERATORS.get("message_ablate")().run(ctx)


def test_thought_truncate_produces_prefixes(tmp_path):
    ep = _episode(writes=[("thoughts.md", "first\nsecond\nthird")])
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    OPERATORS.get("thought_truncate")().run(ctx)
    contents = [iv.new_action.args["content"] for _e, iv in ctx.candidates]
    assert contents == ["first", "first\nsecond"]


def test_clause_perturb_emits_line_patches(tmp_path):
    ep = _episode(writes=[("query.sql", "SELECT a\nFROM t\nWHERE x > 1")])
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    OPERATORS.get("clause_perturb")(
        path="query.sql", patches=[{"line": 2, "text": "WHERE x > 0"}]
    ).run(ctx)
    ((_e, iv),) = ctx.candidates
    assert iv.type == InterventionType.TOOL_ARGUMENT_EDIT
    assert iv.edits[0].patches[0].line == 2


def test_her_relabel_writes_observed_rows(tmp_path):
    ep = _episode(writes=[("a.py", "x = 1")], observation="wrote a.py")
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    OPERATORS.get("her_relabel")().run(ctx)
    rows = [
        json.loads(line)
        for line in Path(ctx.exports["her_sft"]).read_text().splitlines()
        if line.strip()
    ]
    assert rows and all(r["evidence_tier"] == "OBSERVED" for r in rows)
    assert all(r["prompt"].startswith("[goal:") for r in rows)


def test_credit_ate_scores_steps_offline(tmp_path):
    ep = _episode()
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    ctx.units = [_unit(ep, step=0, flipped=True), _unit(ep, step=0, flipped=False)]
    OPERATORS.get("credit_ate")().run(ctx)
    rows = [
        json.loads(line)
        for line in Path(ctx.exports["credit_ate"]).read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["ate"] == 0.5 and rows[0]["n_interventions"] == 2


def test_process_rewards_labels_critical_vs_harmless(tmp_path):
    ep = _episode()
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    ctx.units = [_unit(ep, step=0, flipped=True), _unit(ep, step=1, flipped=False)]
    OPERATORS.get("process_rewards")().run(ctx)
    rows = [
        json.loads(line)
        for line in Path(ctx.exports["process_rewards"]).read_text().splitlines()
        if line.strip()
    ]
    assert {r["label"] for r in rows} == {"critical", "harmless"}
    assert [r["reward"] for r in rows] == [1.0, 0.0]


# --------------------------- engine operators -------------------------------


def test_fix_table_source_loads_curated_fixes(tmp_path):
    table = tmp_path / "fixes.json"
    table.write_text(
        json.dumps({"t1": [{"tool": "write_file", "args": {"path": "a.py", "content": "ok"}}]})
    )
    ctx = OpContext(workdir=tmp_path, episodes=[_episode("t1")])
    OPERATORS.get("fix_table")(path=str(table)).run(ctx)
    assert len(ctx.sources) == 1
    proposals = ctx.sources[0].propose(ctx.episodes[0])
    assert proposals and proposals[0].new_action.args["content"] == "ok"


def test_export_observational_writes_views(tmp_path):
    ep = _episode(writes=[("a.py", "x = 1")])
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    OPERATORS.get("export_observational")().run(ctx)
    assert ctx.exports and all(Path(p).exists() for p in ctx.exports.values())
