from causal_data_juicer.runtime.agent import ScriptedPolicy, ScriptedStep
from causal_data_juicer.sdk.schemas import Snapshot, ToolCall
from causal_data_juicer.store.blob import tree_digest
from causal_data_juicer.store.dag import select_checkpoints


def _snaps(episode_id, steps):
    return [Snapshot(episode_id=episode_id, step_index=i, tree_digest=f"d{i}")
            for i in steps]


def test_select_checkpoints_policies():
    snaps = _snaps("ep1", [0, 1, 2, 3, 4])
    assert len(select_checkpoints(snaps, "every")) == 5
    assert [s.step_index for s in select_checkpoints(snaps, "first")] == [0]
    assert [s.step_index for s in select_checkpoints(snaps, "every_k:2")] == [0, 2, 4]


def test_fork_at_sparse_reconstructs_dense_state(collector, replayer, ws_root):
    """Prefix re-execution from step 0 must rebuild the exact tree that
    the dense per-step snapshot recorded."""
    ws = ws_root / "mini"
    ws.mkdir()
    (ws / "test_solution.py").write_text(
        "from solution import inc\n\ndef test_inc():\n    assert inc(1) == 2\n")
    policy = ScriptedPolicy([
        ScriptedStep(action=ToolCall(tool="write_file",
                                     args={"path": "notes.txt", "content": "step0\n"})),
        ScriptedStep(action=ToolCall(tool="write_file",
                                     args={"path": "solution.py",
                                           "content": "def inc(x):\n    return x + 1\n"})),
        ScriptedStep(action=ToolCall(tool="run_pytest", args={})),
    ])
    episode, snapshots = collector.run_episode("mini", "mini", ws, policy)
    assert len(snapshots) == 3

    sparse = select_checkpoints(snapshots, "first")
    for target in (1, 2):
        workspace, prefix = replayer.fork_at(episode, sparse, target)
        dense = next(s for s in snapshots if s.step_index == target)
        assert tree_digest(workspace) == dense.tree_digest
        assert prefix == target
        replayer.sandbox.dispose(workspace)

    # dense set needs no prefix re-execution
    workspace, prefix = replayer.fork_at(episode, snapshots, 2)
    assert prefix == 0
    replayer.sandbox.dispose(workspace)
