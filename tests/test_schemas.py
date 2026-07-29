from causeforge.sdk.schemas import (
    ArgEdit,
    CostLedger,
    EvidenceTier,
    Intervention,
    InterventionType,
    ToolCall,
)


def test_evidence_tier_is_ordered():
    assert EvidenceTier.OBSERVED < EvidenceTier.SUGGESTED
    assert EvidenceTier.SUGGESTED < EvidenceTier.COUNTERFACTUAL_VALIDATED
    assert EvidenceTier.COUNTERFACTUAL_VALIDATED < EvidenceTier.REPRODUCIBLE
    assert EvidenceTier.REPRODUCIBLE < EvidenceTier.MINIMAL
    assert EvidenceTier.MINIMAL < EvidenceTier.TRAINING_VALIDATED


def test_cost_ledger_merge():
    a, b = CostLedger(), CostLedger()
    a.charge_llm(100, 50, dollars=0.01)
    b.charge_tool(1.5)
    b.replay_runs += 1
    a.merge(b)
    assert a.llm_calls == 1 and a.tokens_in == 100 and a.tokens_out == 50
    assert a.tool_calls == 1 and a.wall_time_s == 1.5
    assert a.replay_runs == 1 and a.dollars == 0.01


def test_effect_signature_dedups_identical_edits():
    def make():
        return Intervention(
            type=InterventionType.TOOL_ARGUMENT_EDIT,
            target_step=0,
            edits=[ArgEdit(arg="path", op="set", value="solution.py")],
        )

    a, b = make(), make()
    assert a.id != b.id
    assert a.effect_signature() == b.effect_signature()

    c = make()
    c.edits[0].value = "other.py"
    assert c.effect_signature() != a.effect_signature()


def test_tool_call_signature_stable():
    a = ToolCall(tool="write_file", args={"path": "x", "content": "y"})
    b = ToolCall(tool="write_file", args={"path": "x", "content": "y"})
    assert a.signature() == b.signature()
