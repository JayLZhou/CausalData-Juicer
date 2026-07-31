import json
import sys

from causal_data_juicer.runtime.envs import (
    ENV_POINTER,
    EnvManager,
    TaskEnv,
    resolve_python,
    write_env_pointer,
)


def test_pointer_roundtrip(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    assert resolve_python(ws) == sys.executable  # no pointer -> own interpreter
    write_env_pointer(ws, tmp_path / "someenv" / "bin" / "python")
    assert resolve_python(ws) == str(tmp_path / "someenv" / "bin" / "python")


def test_env_manager_builds_once_and_freezes(tmp_path):
    mgr = EnvManager(tmp_path / "envs")
    env = TaskEnv(name="bare")  # no extra pins: fast build, still installs pytest
    python = mgr.ensure(env)
    assert python.exists()
    prov = mgr.provenance(env)
    assert any(line.lower().startswith("pytest") for line in prov["frozen"])
    marker = tmp_path / "envs" / "bare" / ".causal_data_juicer_ready.json"
    before = marker.stat().st_mtime_ns
    assert mgr.ensure(env) == python  # second call is a no-op
    assert marker.stat().st_mtime_ns == before


def test_verifier_uses_pointer_interpreter(tmp_path, verifier):
    """A workspace pointing at a broken interpreter must fail verification —
    proof that the pointer, not our own python, runs the tests."""
    from causal_data_juicer.sdk.schemas import CostLedger

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "test_x.py").write_text("def test_ok():\n    assert True\n")
    outcome = verifier.evaluate(ws, CostLedger())
    assert outcome.success

    (ws / ENV_POINTER).write_text(json.dumps({"python": str(tmp_path / "missing" / "python")}))
    try:
        outcome = verifier.evaluate(ws, CostLedger())
        success = outcome.success
    except FileNotFoundError:
        success = False
    assert not success
