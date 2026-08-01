import json
import sys

from pathlib import Path

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
    write_env_pointer(ws, Path(sys.executable), name="self", pins=[])
    assert resolve_python(ws) == sys.executable  # recorded existing path wins


def test_env_manager_builds_once_and_freezes(tmp_path):
    mgr = EnvManager(tmp_path / "envs")
    env = TaskEnv(name="bare")  # no extra pins: fast build, still installs pytest
    python = mgr.ensure(env)
    assert python.exists()
    prov = mgr.provenance(env)
    assert any(line.lower().startswith("pytest") for line in prov["frozen"])
    marker = tmp_path / "envs" / "bare" / ".causeforge_ready.json"
    before = marker.stat().st_mtime_ns
    assert mgr.ensure(env) == python  # second call is a no-op
    assert marker.stat().st_mtime_ns == before


def test_resolution_chain_and_fallback(tmp_path, verifier, recwarn):
    """Pointer v2 semantics: recorded path wins; a stale path with a
    known env name resolves to the local env; a stale path with no
    identity falls back to our interpreter WITH a warning (the engine
    keeps working after a repo move — the portability bug class)."""
    import json
    import warnings

    from causal_data_juicer.sdk.schemas import CostLedger

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "test_x.py").write_text("def test_ok():\n    assert True\n")

    # stale path, no identity -> warn + fallback, verification still runs
    (ws / ENV_POINTER).write_text(json.dumps({"python": str(tmp_path / "gone" / "python")}))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        outcome = verifier.evaluate(ws, CostLedger())
    assert outcome.success
    assert any("stale" in str(w.message) for w in caught)

    # stale path + env identity -> resolves to the local bench_envs twin
    local = tmp_path / "bench_envs" / "mini-env" / "bin"
    local.mkdir(parents=True)
    (local / "python").symlink_to(sys.executable)
    (ws / ENV_POINTER).write_text(json.dumps(
        {"python": str(tmp_path / "gone" / "python"), "env_name": "mini-env"}))
    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert resolve_python(ws) == str(local / "python")
    finally:
        os.chdir(cwd)
