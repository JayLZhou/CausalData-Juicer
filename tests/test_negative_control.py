"""Instrument negative controls.

The 100% flip-repro / digest-match numbers in claims.md are earned by a
gate, not assumed.  Two properties pin down exactly what that gate does:

1. OUTCOME-flaky environments (state leaking outside the snapshot
   boundary, nondeterministic verdicts) are REJECTED: the control branch
   cannot reproduce the recorded outcome, the unit stays SUGGESTED and
   branch B never runs.
2. Content noise with stable outcomes (timestamps inside failure
   messages) is ACCEPTED — by design.  The causal claim lives at
   outcome granularity: the observation digest normalizes run_pytest to
   its pass/fail summary, so cosmetic nondeterminism cannot poison a
   unit whose outcome is deterministic.
"""
from causeforge.runtime.agent import ScriptedPolicy, ScriptedStep
from causeforge.sdk.schemas import (
    ArgEdit,
    EvidenceTier,
    Intervention,
    InterventionType,
    ToolCall,
)

FIX = "def stamp():\n    return 'fixed'\n"


def _episode(collector, ws_root, name, test_content, solution_content):
    ws = ws_root / name
    ws.mkdir()
    (ws / "test_solution.py").write_text(test_content)
    policy = ScriptedPolicy([
        ScriptedStep(action=ToolCall(tool="write_file",
                                     args={"path": "solution.py",
                                           "content": solution_content})),
        ScriptedStep(action=ToolCall(tool="run_pytest", args={})),
    ])
    return collector.run_episode(name, name, ws, policy)


def _fix():
    return Intervention(type=InterventionType.TOOL_ARGUMENT_EDIT, target_step=0,
                        edits=[ArgEdit(arg="content", op="set", value=FIX)])


def test_gate_rejects_outcome_flaky_environment(collector, replayer, ws_root, tmp_path):
    """Hidden state OUTSIDE the snapshot boundary: a counter the test
    reads and bumps on every visit.  Fails on the recorded run, passes on
    the control replay -> outcome mismatch -> rejected."""
    counter = tmp_path / "external-state.txt"
    poison_test = (
        "import pathlib\n"
        f"COUNTER = pathlib.Path({str(counter)!r})\n"
        "\n"
        "\n"
        "def test_flaky():\n"
        "    n = int(COUNTER.read_text()) if COUNTER.exists() else 0\n"
        "    COUNTER.write_text(str(n + 1))\n"
        "    # 'environment changes after the recorded run': the recorded\n"
        "    # episode's two visits (step + verifier) fail, later ones pass\n"
        "    assert n >= 2\n"
    )
    episode, snapshots = _episode(collector, ws_root, "flaky", poison_test,
                                  "def stamp():\n    return 'nope'\n")
    assert not episode.outcome.success  # recorded run: visits 0 and 1 -> fails

    unit = replayer.paired_replay(episode, snapshots, _fix(), n_repro=3)
    assert unit.original_replay_match is False  # control saw a different verdict
    assert unit.tier == EvidenceTier.SUGGESTED
    assert unit.intervened_outcome is None      # branch B never ran: no spend on a broken instrument


def test_gate_is_outcome_grained_not_text_grained(collector, replayer, ws_root):
    """Timestamps inside failure text vary per replay, but the verdict is
    deterministic — the unit validates, because the causal claim is about
    outcomes, not log bytes."""
    noisy_test = (
        "import time\n"
        "from solution import stamp\n"
        "\n"
        "\n"
        "def test_stamp():\n"
        "    assert stamp() == 'fixed', f'got {stamp()} at {time.time_ns()}'\n"
    )
    episode, snapshots = _episode(collector, ws_root, "noisy", noisy_test,
                                  "def stamp():\n    return 'nope'\n")
    assert not episode.outcome.success

    unit = replayer.paired_replay(episode, snapshots, _fix(), n_repro=3)
    assert unit.original_replay_match is True
    assert unit.flipped and unit.tier == EvidenceTier.REPRODUCIBLE