"""Unit coverage for the isolation layer's pure logic — the parts that need
no live runtime: container argv construction, level descriptions, probe
fallbacks, and the verify-claims orchestration path (with the heavyweight
demo/subprocess calls stubbed; the real end-to-end run is a separate CI
step, `cdj verify-claims`)."""

import io
from contextlib import redirect_stdout

from causal_data_juicer.runtime.exec_backend import Capabilities, describe, wrap


def _container_caps():
    return Capabilities("container", {"runtime": "podman", "podman": "/usr/bin/podman"})


def test_container_wrap_builds_a_locked_down_argv(tmp_path):
    argv = wrap(["pytest", "-q"], tmp_path, caps=_container_caps())
    joined = " ".join(argv)
    assert argv[0] == "/usr/bin/podman"
    assert "--network=none" in argv
    assert "--cap-drop" in argv and "ALL" in argv
    assert "--read-only" in argv
    assert "no-new-privileges" in joined
    assert "--pids-limit" in argv
    assert f"{tmp_path.resolve()}:/ws:rw" in joined  # workspace only
    assert argv[-2:] == ["pytest", "-q"]


def test_container_wrap_respects_memory_limit_override(tmp_path):
    argv = wrap(["true"], tmp_path, caps=_container_caps(), limits={"as_bytes": 123456})
    assert "123456" in argv


def test_describe_all_levels():
    assert "podman" in describe(_container_caps())
    assert "NO isolation" in describe(Capabilities("none", {}))
    netns = describe(Capabilities("netns", {"apparmor": "some-profile"}))
    assert "NO filesystem isolation" in netns and "some-profile" in netns


def test_verify_claims_orchestration_not_run_path(monkeypatch, tmp_path):
    """Full verify_claims() flow with stubs: demo passes, pytest slices pass,
    replay pack absent → B1 must be NOT_RUN and strict exit nonzero."""
    import subprocess

    import causal_data_juicer.verify_claims as vc

    monkeypatch.setattr(
        "causal_data_juicer.pipeline.run_demo",
        lambda out, n_repro: {
            "flip_repro_rate": 1.0,
            "flip_repro_detail": "6/6",
            "control_digest_match_rate": 1.0,
        },
    )

    class FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeProc())
    code = vc.verify_claims(repo_root=tmp_path, strict=True)  # no replay pack in tmp
    assert code == 1
    assert vc.verify_claims(repo_root=tmp_path, strict=False) == 0


def test_verify_claims_orchestration_pack_present_path(monkeypatch, tmp_path):
    """With a replay pack on disk and stubbed executions, B1 executes and the
    strict run exits 0 — the full-pass message path."""
    import json
    import subprocess

    import causal_data_juicer.verify_claims as vc

    (tmp_path / "replay-packs" / "step-dpo" / "llm_cache").mkdir(parents=True)
    (tmp_path / "replay-packs" / "step-dpo" / "base-run").mkdir()
    (tmp_path / "bench_envs" / "pydantic-new").mkdir(parents=True)

    monkeypatch.setattr(
        "causal_data_juicer.pipeline.run_demo",
        lambda out, n_repro: {
            "flip_repro_rate": 1.0,
            "flip_repro_detail": "6/6",
            "control_digest_match_rate": 1.0,
        },
    )

    class FakeProc:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {"episodes": 19, "sampled_branches": 46, "flipping_branches": 7, "step_dpo_pairs": 12}
        )

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeProc())
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = vc.verify_claims(repo_root=tmp_path, strict=True)
    assert code == 0
    assert "All required claims executed and passed" in buf.getvalue()


def test_context_skips_oversized_and_unreadable_files(tmp_path):
    from causal_data_juicer.runtime.context import build_context, context_manifest

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "big.py").write_text("x = 1\n" * 5000)  # over max_file
    (ws / "bin.py").write_bytes(b"\xff\xfe\x00broken")  # undecodable
    (ws / "ok.py").write_text("y = 2\n")
    subdir = ws / "nested"
    subdir.mkdir()  # bare directory: not a file
    ctx = build_context(ws)
    assert "y = 2" in ctx
    assert "x = 1" not in ctx
    assert context_manifest(ws) == ["ok.py"]


def test_context_total_budget_truncates(tmp_path):
    from causal_data_juicer.runtime.context import build_context

    ws = tmp_path / "ws"
    ws.mkdir()
    for i in range(9):
        (ws / f"f{i}.py").write_text(f"data_{i} = {'z' * 2000}\n")
    ctx = build_context(ws, max_file=4000, max_total=5000)
    assert 0 < len(ctx) <= 5000
