import pytest

from causal_data_juicer.runtime.tools import EXTERNAL_OBS_PLACEHOLDER, ToolExecutor
from causal_data_juicer.sdk.schemas import CostLedger, ToolCall
from causal_data_juicer.store.blob import BlobStore, tree_digest


def test_tree_digest_deterministic_and_ignores_caches(tmp_path):
    ws = tmp_path / "ws"
    (ws / "pkg").mkdir(parents=True)
    (ws / "a.py").write_text("x = 1\n")
    (ws / "pkg" / "b.py").write_text("y = 2\n")
    d1 = tree_digest(ws)
    (ws / "__pycache__").mkdir()
    (ws / "__pycache__" / "junk.pyc").write_bytes(b"\x00")
    assert tree_digest(ws) == d1
    (ws / "a.py").write_text("x = 2\n")
    assert tree_digest(ws) != d1


def test_blob_store_roundtrip(tmp_path):
    store = BlobStore(tmp_path / "blobs")
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("hello")
    digest = store.put_tree(ws)
    assert store.has(digest)
    restored = store.restore_tree(digest, tmp_path / "restored")
    assert (restored / "f.txt").read_text() == "hello"
    assert tree_digest(restored) == digest


def test_write_file_cannot_escape_workspace(registry, tmp_path):
    """Escapes are refused; the refusal is an observation (agents recover),
    and nothing lands outside the workspace."""
    executor = ToolExecutor(registry, mode="live")
    ws = tmp_path / "ws"
    ws.mkdir()
    call = ToolCall(tool="write_file", args={"path": "../evil.txt", "content": "x"})
    obs, _ = executor.execute(ws, call, CostLedger())
    assert obs.startswith("[tool-error] ValueError")
    assert not (tmp_path / "evil.txt").exists()


def test_external_tool_is_mocked_in_replay_and_digest_is_mode_invariant(registry, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    call = ToolCall(tool="send_report", args={"message": "hi"})
    live_obs, live_digest = ToolExecutor(registry, "live").execute(ws, call, CostLedger())
    replay_obs, replay_digest = ToolExecutor(registry, "replay").execute(ws, call, CostLedger())
    assert "report sent" in live_obs
    assert "dry-run mock" in replay_obs          # never truly executed in replay
    assert live_digest == replay_digest          # digests normalized via placeholder
    assert EXTERNAL_OBS_PLACEHOLDER not in live_obs
