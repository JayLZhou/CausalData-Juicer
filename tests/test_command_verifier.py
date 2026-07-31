"""CommandVerifier: the generality escape hatch — any executable
workload becomes verifiable, and therefore flip-attributable."""
from causeforge.runtime.agent import ScriptedPolicy, ScriptedStep
from causeforge.runtime.collector import Collector
from causeforge.runtime.verifier import CommandVerifier
from causeforge.sdk.schemas import (
    ArgEdit,
    CostLedger,
    EvidenceTier,
    Intervention,
    InterventionType,
    ToolCall,
)


def test_exit_code_semantics(tmp_path):
    verifier = CommandVerifier(["{python}", "check.py"])
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "check.py").write_text("raise SystemExit(1)")
    assert verifier.evaluate(ws, CostLedger()).success is False
    (ws / "check.py").write_text("print('fine')")
    outcome = verifier.evaluate(ws, CostLedger())
    assert outcome.success is True and "fine" in outcome.detail


def test_full_loop_with_command_verifier(registry, blobs, replayer, ws_root, tmp_path):
    """A non-pytest workload (plain script exit code) goes through
    collect -> paired replay -> REPRODUCIBLE, engine unchanged."""
    verifier = CommandVerifier(["{python}", "build.py"])
    collector = Collector(registry, blobs, verifier)
    replayer.verifier = verifier

    ws = ws_root / "cmd"
    ws.mkdir()
    (ws / "build.py").write_text(
        "import config\nraise SystemExit(0 if config.MODE == 'prod' else 1)\n")
    policy = ScriptedPolicy([
        ScriptedStep(action=ToolCall(tool="write_file",
                                     args={"path": "config.py", "content": "MODE = 'dev'\n"})),
    ])
    episode, snapshots = collector.run_episode("cmd-task", "set prod mode", ws, policy)
    assert not episode.outcome.success

    fix = Intervention(
        type=InterventionType.TOOL_ARGUMENT_EDIT, target_step=0,
        edits=[ArgEdit(arg="content", op="set", value="MODE = 'prod'\n")],
    )
    unit = replayer.paired_replay(episode, snapshots, fix, n_repro=3)
    assert unit.flipped and unit.tier == EvidenceTier.REPRODUCIBLE
