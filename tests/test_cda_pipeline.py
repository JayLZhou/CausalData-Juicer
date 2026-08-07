"""Identify -> Generate -> Filter -> Validate, with the execution gate intact.

The load-bearing assertion in this file is negative: constraint filtering
must NOT be able to mint causal evidence. A branch that satisfies every
hard constraint reaches CONSTRAINT_VALIDATED and stops there; only a real
paired replay goes higher.
"""

import json

import pytest

import causal_data_juicer.ops  # noqa: F401
from causal_data_juicer.ops.base_op import OPERATORS, OpContext
from causal_data_juicer.sdk.schemas import (
    CausalUnit,
    Episode,
    EvidenceTier,
    Intervention,
    InterventionType,
    Outcome,
    SiteKind,
    Step,
    ToolCall,
    parse_tier,
)


def _episode(task_id="t1", writes=(), success=False):
    steps = [
        Step(index=i, action=ToolCall(tool="write_file", args={"path": p, "content": c}))
        for i, (p, c) in enumerate(writes)
    ]
    return Episode(
        task_id=task_id,
        task_description="demo",
        steps=steps,
        outcome=Outcome(success=success, failed=0 if success else 1),
    )


def _mapped(tmp_path, ep, **params):
    ctx = OpContext(workdir=tmp_path, episodes=[ep])
    OPERATORS.get("intervention_site_mapper")(**params).run(ctx)
    return ctx


# --------------------------- the evidence ladder ----------------------------


def test_constraint_rung_sits_between_suggested_and_counterfactual():
    assert (
        EvidenceTier.SUGGESTED
        < EvidenceTier.CONSTRAINT_VALIDATED
        < EvidenceTier.COUNTERFACTUAL_VALIDATED
    )


def test_legacy_integer_tiers_still_mean_what_they_meant():
    """Runs written before the rung existed stored 0-5. Reinterpreting a
    stored 2 as the new rung would silently downgrade the whole corpus."""
    assert parse_tier(2) is EvidenceTier.COUNTERFACTUAL_VALIDATED
    assert parse_tier(4) is EvidenceTier.MINIMAL
    unit = CausalUnit.model_validate_json(
        json.dumps(
            {
                "episode_id": "ep_x",
                "task_id": "t",
                "intervention": {
                    "type": "ACTION_REPLACE",
                    "target_step": 0,
                    "new_action": {"tool": "write_file", "args": {"path": "a", "content": "b"}},
                },
                "original_outcome": {"success": False},
                "tier": 4,
            }
        )
    )
    assert unit.tier is EvidenceTier.MINIMAL


def test_units_persist_the_tier_name_not_a_fragile_integer(tmp_path):
    unit = CausalUnit(
        episode_id="e",
        task_id="t",
        intervention=Intervention(
            type=InterventionType.ACTION_REPLACE,
            target_step=0,
            new_action=ToolCall(tool="write_file", args={"path": "a", "content": "b"}),
        ),
        original_outcome=Outcome(success=False),
        tier=EvidenceTier.CONSTRAINT_VALIDATED,
    )
    assert json.loads(unit.model_dump_json())["tier"] == "CONSTRAINT_VALIDATED"
    assert CausalUnit.model_validate_json(unit.model_dump_json()).tier is (
        EvidenceTier.CONSTRAINT_VALIDATED
    )


# ------------------------------- identify -----------------------------------


def test_site_mapper_types_the_variables_it_finds(tmp_path):
    ep = _episode(
        writes=[
            ("config.yaml", "version: latest\ntimeout: 30"),
            ("thoughts.md", "first idea\nsecond idea"),
            ("context.md", "doc A\n\ndoc B"),
            ("notes.md", "pydantic requires v2"),
        ]
    )
    ctx = _mapped(tmp_path, ep)
    kinds = {s["kind"] for s in ctx.meta["sites"]}
    assert {
        SiteKind.TOOL_ARGUMENT.value,
        SiteKind.STRUCTURED_FIELD.value,
        SiteKind.RATIONALE.value,
        SiteKind.TEXT_SPAN.value,
        SiteKind.SEMANTIC_TRIPLE.value,
        SiteKind.AGENT_ACTION.value,
    } <= kinds


def test_sites_carry_invariants_and_descendants(tmp_path):
    ctx = _mapped(tmp_path, _episode(writes=[("config.yaml", "version: latest")]))
    site = next(s for s in ctx.meta["sites"] if s["variable"] == "field.version")
    assert site["current_value"] == "latest"
    assert site["invariants"] == ["task", "repository", "user_intent"]
    assert site["possible_descendants"] == ["tool_output", "next_action", "outcome"]
    assert 0.0 <= site["influence_score"] <= 1.0


def test_site_kinds_can_be_restricted(tmp_path):
    ctx = _mapped(
        tmp_path, _episode(writes=[("config.yaml", "version: latest")]), kinds=["StructuredField"]
    )
    assert {s["kind"] for s in ctx.meta["sites"]} == {"StructuredField"}


# ------------------------------- generate -----------------------------------


def test_do_mapper_requires_sites_first(tmp_path):
    ctx = OpContext(workdir=tmp_path, episodes=[_episode()])
    with pytest.raises(ValueError, match="intervention_site_mapper"):
        OPERATORS.get("do_counterfactual_mapper")().run(ctx)


def test_do_mapper_changes_one_variable_and_records_provenance(tmp_path):
    ctx = _mapped(
        tmp_path, _episode(writes=[("config.yaml", "version: latest")]), kinds=["StructuredField"]
    )
    OPERATORS.get("do_counterfactual_mapper")(
        strategy="retrieve_edit", values=["2.11.7"], seed=7
    ).run(ctx)
    branches = ctx.services["branches"]
    assert branches
    br = branches[0]
    content = br.intervention.new_action.args["content"]
    assert "version: 2.11.7" in content
    assert br.provenance.strategy == "retrieve_edit" and br.provenance.seed == 7
    assert br.provenance.regenerated_descendants == ["tool_output", "next_action", "outcome"]
    assert br.invariants and br.tier is EvidenceTier.SUGGESTED  # generation proves nothing


def test_do_mapper_mask_edit_blanks_only_the_site(tmp_path):
    ctx = _mapped(
        tmp_path,
        _episode(writes=[("config.yaml", "version: latest\ntimeout: 30")]),
        kinds=["StructuredField"],
    )
    OPERATORS.get("do_counterfactual_mapper")(strategy="mask_edit").run(ctx)
    for br in ctx.services["branches"]:
        content = br.intervention.new_action.args["content"]
        assert len(content.splitlines()) == 2  # structure intact
        assert br.intervention.new_action.args["path"] == "config.yaml"


def test_do_mapper_descendant_regeneration_needs_an_endpoint(tmp_path):
    ctx = _mapped(tmp_path, _episode(writes=[("config.yaml", "version: latest")]))
    with pytest.raises(ValueError, match="base_url"):
        OPERATORS.get("do_counterfactual_mapper")(strategy="descendant_regeneration").run(ctx)


# -------------------------------- filter ------------------------------------


def _generate(tmp_path, **do_params):
    ctx = _mapped(
        tmp_path,
        _episode(writes=[("config.yaml", "version: latest\ntimeout: 30")]),
        kinds=["StructuredField"],
    )
    OPERATORS.get("do_counterfactual_mapper")(**do_params).run(ctx)
    return ctx


def test_filter_promotes_only_to_the_constraint_rung(tmp_path):
    ctx = _generate(tmp_path, strategy="retrieve_edit", values=["2.11.7"])
    OPERATORS.get("counterfactual_validity_filter")().run(ctx)
    accepted = ctx.services["branches"]
    assert accepted, "a well-formed single-variable edit should pass"
    for br in accepted:
        assert br.tier is EvidenceTier.CONSTRAINT_VALIDATED
        assert br.tier < EvidenceTier.COUNTERFACTUAL_VALIDATED  # the whole point
        assert br.validation.accepted and br.validation.failed_at is None


def test_filter_rejects_a_no_op_edit_with_provenance(tmp_path):
    ctx = _generate(tmp_path, strategy="retrieve_edit", values=["latest"])  # same value
    OPERATORS.get("counterfactual_validity_filter")().run(ctx)
    rejected = ctx.services["rejected_branches"]
    assert rejected
    assert rejected[0].validation.failed_at == "intervention_fidelity"
    assert rejected[0].validation.reason
    assert rejected[0].tier is EvidenceTier.SUGGESTED  # never promoted


def test_filter_rejects_when_an_invariant_moves(tmp_path):
    ctx = _generate(tmp_path, strategy="retrieve_edit", values=["2.11.7"])
    br = ctx.services["branches"][0]
    # tamper: the artifact's identity (its path) is an invariant
    br.intervention.new_action = ToolCall(
        tool="write_file", args={"path": "other.yaml", "content": "version: 2.11.7"}
    )
    OPERATORS.get("counterfactual_validity_filter")().run(ctx)
    failed = [b.validation.failed_at for b in ctx.services["rejected_branches"]]
    assert "invariant_preservation" in failed


def test_filter_rejects_unexecutable_actions(tmp_path):
    ctx = _generate(tmp_path, strategy="retrieve_edit", values=["2.11.7"])
    ctx.services["branches"][0].intervention.new_action = ToolCall(
        tool="not_a_registered_tool", args={"path": "config.yaml", "content": "x"}
    )
    OPERATORS.get("counterfactual_validity_filter")().run(ctx)
    assert "schema_validity" in [b.validation.failed_at for b in ctx.services["rejected_branches"]]


def test_filter_records_soft_scores_without_gating_on_them(tmp_path):
    ctx = _generate(tmp_path, strategy="retrieve_edit", values=["2.11.7"])
    OPERATORS.get("counterfactual_validity_filter")().run(ctx)
    v = ctx.services["branches"][0].validation
    assert 0.0 <= v.semantic_proximity <= 1.0 and 0.0 <= v.minimality <= 1.0
    assert v.verifier_confidence is None  # only a replay can fill this in


# ------------------------------- validate -----------------------------------


def test_selector_clusters_by_effect_signature_and_respects_budget(tmp_path):
    ctx = _generate(tmp_path, strategy="retrieve_edit", values=["2.11.7"])
    OPERATORS.get("counterfactual_validity_filter")(drop_identical=False).run(ctx)
    n_accepted = len(ctx.services["branches"])
    OPERATORS.get("replay_promotion_selector")(budget=1).run(ctx)
    meta = ctx.meta["replay_promotion_selector"]
    assert meta["requested"] == 1 <= n_accepted
    assert meta["spent"] <= meta["budget"]
    assert ctx.services["replay_requests"][0].is_cluster_representative


def test_selector_queues_candidates_for_the_engine(tmp_path):
    ctx = _generate(tmp_path, strategy="retrieve_edit", values=["2.11.7"])
    OPERATORS.get("counterfactual_validity_filter")().run(ctx)
    OPERATORS.get("replay_promotion_selector")(budget=5).run(ctx)
    assert ctx.candidates and all(isinstance(iv, Intervention) for _ep, iv in ctx.candidates)


def test_selector_records_what_the_budget_could_not_buy(tmp_path):
    ctx = _generate(tmp_path, strategy="mask_edit")
    OPERATORS.get("counterfactual_validity_filter")(drop_identical=False).run(ctx)
    OPERATORS.get("replay_promotion_selector")(budget=1).run(ctx)
    meta = ctx.meta["replay_promotion_selector"]
    assert meta["clusters"] >= meta["requested"]
    if meta["clusters"] > meta["requested"]:
        assert meta["skipped_total"] > 0, "unfunded clusters must be reported, not dropped"


def test_selector_is_a_no_op_without_branches(tmp_path):
    ctx = OpContext(workdir=tmp_path, episodes=[_episode()])
    OPERATORS.get("replay_promotion_selector")().run(ctx)
    assert ctx.meta["replay_promotion_selector"]["requested"] == 0


def test_provenance_attaches_generation_and_never_raises_a_tier(tmp_path):
    """The audit trail must survive execution: a finished unit should say it
    came from a model, which constraints it cleared, and which site moved —
    while its tier still comes only from what was executed."""
    ctx = _generate(tmp_path, strategy="retrieve_edit", values=["2.11.7"])
    OPERATORS.get("counterfactual_validity_filter")().run(ctx)
    branch = ctx.services["branches"][0]
    assert branch.tier is EvidenceTier.CONSTRAINT_VALIDATED

    ep = ctx.episodes[0]
    unit = CausalUnit(
        episode_id=ep.id,
        task_id=ep.task_id,
        intervention=branch.intervention,  # same intervention object id
        original_outcome=Outcome(success=False, failed=1),
        intervened_outcome=Outcome(success=False, failed=1),  # it did NOT flip
        flipped=False,
        tier=EvidenceTier.SUGGESTED,
    )
    ctx.units = [unit]
    OPERATORS.get("attach_generation_provenance")().run(ctx)

    assert unit.provenance["generation"]["strategy"] == "retrieve_edit"
    assert unit.provenance["constraint_validation"]["accepted"] is True
    assert unit.provenance["site"]["variable"].startswith("field.")
    assert unit.provenance["generated_tier_before_execution"] == "CONSTRAINT_VALIDATED"
    # the gate: constraint validation does not survive as causal evidence
    assert unit.tier is EvidenceTier.SUGGESTED
    assert ctx.meta["attach_generation_provenance"]["promoted_by_execution"] == 0


def test_effect_signature_deduplicator_collapses_paraphrases(tmp_path):
    """Two strategies proposing the identical edit are one experiment; the
    replay budget must not pay twice for it."""
    ctx = _mapped(
        tmp_path, _episode(writes=[("config.yaml", "version: latest")]), kinds=["StructuredField"]
    )
    # mask_edit and retrieve_edit with the empty value produce the same effect
    OPERATORS.get("do_counterfactual_mapper")(
        strategy=["mask_edit", "retrieve_edit"], values=[""]
    ).run(ctx)
    before = len(ctx.services["branches"])
    assert before >= 2
    OPERATORS.get("effect_signature_deduplicator")().run(ctx)
    meta = ctx.meta["effect_signature_deduplicator"]
    assert meta["before"] == before and meta["after"] < before
    assert meta["collapsed"] >= 1
    assert ctx.meta["duplicate_signatures"][0]["duplicates"] >= 1


def test_deduplicator_keeps_distinct_hypotheses(tmp_path):
    ctx = _mapped(
        tmp_path,
        _episode(writes=[("config.yaml", "version: latest\ntimeout: 30")]),
        kinds=["StructuredField"],
    )
    OPERATORS.get("do_counterfactual_mapper")(strategy="mask_edit").run(ctx)
    n = len(ctx.services["branches"])
    OPERATORS.get("effect_signature_deduplicator")().run(ctx)
    assert len(ctx.services["branches"]) == n  # different variables: not duplicates
