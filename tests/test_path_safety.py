"""Path-attack suite for the single path-resolution choke point.

Exists because `_read_file` shipped without any check: `../secret.txt`
(and even absolute paths, via pathlib's `ws / "/etc/x"` behavior) read
host files straight into agent observations.
"""
import os
from pathlib import Path

import pytest

from causal_data_juicer.runtime.paths import WorkspaceEscapeError, resolve_workspace_path
from causal_data_juicer.runtime.tools import _read_file, _write_file


@pytest.fixture()
def ws(tmp_path):
    w = tmp_path / "ws"
    (w / "sub").mkdir(parents=True)
    (w / "inside.txt").write_text("inside")
    (w / "sub" / "deep.txt").write_text("deep")
    (tmp_path / "secret.txt").write_text("CANARY-HOST-SECRET")
    return w


# -- rejection: absolute paths -----------------------------------------------

def test_rejects_absolute_posix(ws):
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, "/etc/passwd")


def test_rejects_absolute_windows(ws):
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, "C:\\Windows\\system32")


def test_pathlib_absolute_join_footgun_is_closed(ws):
    # pathlib: ws / "/abs" silently returns "/abs" — the layer must catch it.
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, str(ws.parent / "secret.txt"))


# -- rejection: dot-dot escapes ----------------------------------------------

def test_rejects_simple_dotdot(ws):
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, "../secret.txt")


def test_rejects_deep_dotdot(ws):
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, "../../../../etc/passwd")


def test_rejects_embedded_dotdot_even_if_it_lands_inside(ws):
    # sub/../inside.txt would resolve inside — still rejected: no ".." ever.
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, "sub/../inside.txt")


# -- rejection: symlink escapes ----------------------------------------------

def test_rejects_final_symlink_pointing_outside(ws, tmp_path):
    os.symlink(tmp_path / "secret.txt", ws / "link.txt")
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, "link.txt")


def test_rejects_final_symlink_outside_even_when_allowed(ws, tmp_path):
    os.symlink(tmp_path / "secret.txt", ws / "link.txt")
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, "link.txt", allow_symlink=True)


def test_allows_final_symlink_inside_only_when_opted_in(ws):
    os.symlink(ws / "inside.txt", ws / "alias.txt")
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, "alias.txt")  # default: no symlinks
    p = resolve_workspace_path(ws, "alias.txt", allow_symlink=True)
    assert p.read_text() == "inside"


def test_rejects_intermediate_symlink_dir_escape(ws, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.txt").write_text("out")
    os.symlink(outside, ws / "linkdir")
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, "linkdir/x.txt")


def test_rejects_intermediate_symlink_even_pointing_inside(ws):
    os.symlink(ws / "sub", ws / "subalias")
    with pytest.raises(WorkspaceEscapeError):
        resolve_workspace_path(ws, "subalias/deep.txt")


# -- allowed paths & modes ----------------------------------------------------

def test_normal_nested_path_resolves(ws):
    p = resolve_workspace_path(ws, "sub/deep.txt", must_exist=True)
    assert p.read_text() == "deep"


def test_nonexistent_path_ok_for_writes(ws):
    p = resolve_workspace_path(ws, "new/dir/file.txt")
    assert str(p).startswith(str(ws))


def test_must_exist_raises_filenotfound(ws):
    with pytest.raises(FileNotFoundError):
        resolve_workspace_path(ws, "missing.txt", must_exist=True)


# -- the actual agent tools use the same rules --------------------------------

def test_read_tool_cannot_escape(ws):
    with pytest.raises(WorkspaceEscapeError):
        _read_file(ws, path="../secret.txt")
    with pytest.raises(WorkspaceEscapeError):
        _read_file(ws, path="/etc/passwd")


def test_read_tool_cannot_follow_symlink_out(ws, tmp_path):
    os.symlink(tmp_path / "secret.txt", ws / "link.txt")
    with pytest.raises(WorkspaceEscapeError):
        _read_file(ws, path="link.txt")


def test_write_tool_cannot_escape(ws):
    with pytest.raises(WorkspaceEscapeError):
        _write_file(ws, path="../evil.txt", content="x")
    assert not (ws.parent / "evil.txt").exists()


def test_tools_still_work_normally(ws):
    assert "wrote" in _write_file(ws, path="sub/new.txt", content="hello")
    assert _read_file(ws, path="sub/new.txt") == "hello"
