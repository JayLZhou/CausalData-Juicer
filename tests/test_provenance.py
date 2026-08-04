from causal_data_juicer.maintenance.provenance import env_fingerprint, needs_revalidation, stamp
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.sdk.schemas import (
    CausalUnit,
    Intervention,
    InterventionType,
    Outcome,
    ToolCall,
)


def _unit():
    return CausalUnit(
        episode_id="ep_x",
        task_id="t",
        intervention=Intervention(
            type=InterventionType.ACTION_REPLACE,
            target_step=0,
            new_action=ToolCall(tool="write_file", args={}),
        ),
        original_outcome=Outcome(success=False),
    )


def test_stamp_and_selective_revalidation():
    registry = default_registry()
    fp = env_fingerprint(registry, "wl-1")
    unit = stamp(_unit(), fp)
    assert needs_revalidation(unit, fp) == []

    drifted = dict(fp, python="9.9.9")
    assert needs_revalidation(unit, drifted) == ["python"]


def test_revalidation_scope_is_the_intersection():
    unit = stamp(_unit(), {"family": "pydantic", "env:pydantic": "aaa", "fixer_model": "qwen-7b"})
    # event tracks env components only; other families' drift is invisible
    current = {"env:pydantic": "aaa", "env:click": "changed!"}
    assert needs_revalidation(unit, current) == []
    # my own family drifting does trigger
    assert needs_revalidation(unit, {"env:pydantic": "bbb"}) == ["env:pydantic"]
    # production metadata outside the event scope never triggers
    assert needs_revalidation(unit, {"env:pydantic": "aaa"}) == []
