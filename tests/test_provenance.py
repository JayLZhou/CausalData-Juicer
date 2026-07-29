from causeforge.maintenance.provenance import env_fingerprint, needs_revalidation, stamp
from causeforge.runtime.tools import default_registry
from causeforge.sdk.schemas import CausalUnit, Intervention, InterventionType, Outcome, ToolCall


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
