"""Reactive continuation: downstream agents re-react to an intervened
message — and the contrast test proves recorded replay alone cannot
express message credit."""
from causal_data_juicer.runtime.collector import Collector
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import PytestVerifier
from causal_data_juicer.sdk.schemas import (
    EvidenceTier,
    Intervention,
    InterventionType,
    ToolCall,
)

TEST = "from solution import f\n\ndef test_f():\n    assert f(3) == 6\n"


class Coder:
    """Deterministic 'downstream agent': implements whatever PLAN says."""

    def next_action(self, task_id, idx, history):
        if idx == 1:
            plan = history[0].action.args["content"]
            body = "return 2 * x" if "double" in plan else "return x"
            return ToolCall(tool="write_file",
                            args={"path": "solution.py",
                                  "content": f"def f(x):\n    {body}\n"}), None
        if idx == 2:
            return ToolCall(tool="run_pytest", args={}), None
        return None


class Team(Coder):
    def __init__(self, plan):
        self.plan = plan

    def next_action(self, task_id, idx, history):
        if idx == 0:
            return ToolCall(tool="write_file",
                            args={"path": "PLAN.md", "content": self.plan}), None
        return super().next_action(task_id, idx, history)


def _collect(blobs, ws_root):
    collector = Collector(default_registry(), blobs, PytestVerifier())
    ws = ws_root / "team"
    ws.mkdir()
    (ws / "test_solution.py").write_text(TEST)
    return collector.run_episode("team", "team task", ws, Team("plan: identity"))


def _message_edit():
    return Intervention(
        type=InterventionType.ACTION_REPLACE, target_step=0,
        new_action=ToolCall(tool="write_file",
                            args={"path": "PLAN.md", "content": "plan: double it"}),
        source="message-edit")


def test_reactive_replay_attributes_the_message(blobs, replayer, ws_root):
    episode, snapshots = _collect(blobs, ws_root)
    assert not episode.outcome.success
    unit = replayer.paired_replay(episode, snapshots, _message_edit(), n_repro=2,
                                  continuation_policy=Coder())
    assert unit.original_replay_match is True
    assert unit.flipped and unit.tier == EvidenceTier.REPRODUCIBLE


def test_recorded_replay_cannot_express_message_credit(blobs, replayer, ws_root):
    """The necessity contrast: without reactive continuation the coder's
    RECORDED action replays verbatim, the new message changes nothing,
    and no flip occurs."""
    episode, snapshots = _collect(blobs, ws_root)
    unit = replayer.paired_replay(episode, snapshots, _message_edit(), n_repro=2)
    assert unit.flipped is False
    assert unit.tier == EvidenceTier.SUGGESTED
