"""Collector + replay engine tests on a minimal 2-step task."""
from causal_data_juicer.runtime.agent import ScriptedPolicy, ScriptedStep
from causal_data_juicer.sdk.schemas import (
    ArgEdit,
    EvidenceTier,
    Intervention,
    InterventionType,
    ToolCall,
)

TEST_FILE = (
    "from solution import double\n\n"
    "def test_double():\n    assert double(2) == 4\n"
)
BAD = "def double(x):\n    return x + x + x\n"
GOOD = "def double(x):\n    return 2 * x\n"


def _collect(collector, ws_root, content, task_id="mini"):
    ws = ws_root / task_id
    ws.mkdir()
    (ws / "test_solution.py").write_text(TEST_FILE)
    policy = ScriptedPolicy([
        ScriptedStep(action=ToolCall(tool="write_file",
                                     args={"path": "solution.py", "content": content})),
        ScriptedStep(action=ToolCall(tool="run_pytest", args={})),
    ])
    return collector.run_episode(task_id, "implement double(x)", ws, policy)


def fix():
    return Intervention(
        type=InterventionType.TOOL_ARGUMENT_EDIT,
        target_step=0,
        edits=[ArgEdit(arg="content", op="set", value=GOOD)],
    )


def test_collector_records_steps_snapshots_and_cost(collector, ws_root):
    episode, snapshots = _collect(collector, ws_root, GOOD)
    assert len(episode.steps) == 2
    assert [s.step_index for s in snapshots] == [0, 1]
    assert episode.outcome.success
    assert episode.cost.llm_calls == 2 and episode.cost.tokens_out > 0
    assert all(s.obs_digest for s in episode.steps)


def test_recorded_replay_is_deterministic(collector, replayer, ws_root):
    episode, snapshots = _collect(collector, ws_root, BAD)
    record = replayer.recorded_replay(episode, snapshots, from_step=0)
    assert record.deterministic_match is True
    assert record.outcome.success is False


def test_paired_replay_validates_flip_to_reproducible(collector, replayer, ws_root):
    episode, snapshots = _collect(collector, ws_root, BAD)
    assert not episode.outcome.success
    unit = replayer.paired_replay(episode, snapshots, fix(), n_repro=3)
    assert unit.original_replay_match is True
    assert unit.flipped and unit.intervened_outcome.success
    assert unit.repro_flips == unit.repro_runs == 3
    assert unit.tier == EvidenceTier.REPRODUCIBLE


def test_non_flipping_candidate_stays_suggested(collector, replayer, ws_root):
    episode, snapshots = _collect(collector, ws_root, BAD)
    noop = Intervention(
        type=InterventionType.TOOL_ARGUMENT_EDIT,
        target_step=0,
        edits=[ArgEdit(arg="content", op="set", value=BAD)],
    )
    unit = replayer.paired_replay(episode, snapshots, noop, n_repro=3)
    assert not unit.flipped
    assert unit.tier == EvidenceTier.SUGGESTED


def test_flip_on_passing_episode_is_not_a_flip(collector, replayer, ws_root):
    episode, snapshots = _collect(collector, ws_root, GOOD)
    unit = replayer.paired_replay(episode, snapshots, fix(), n_repro=1)
    assert not unit.flipped  # nothing to flip: original already succeeds
