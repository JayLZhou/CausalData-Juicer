"""The isolation backend must be *proven*, not configured.

Container-level tests execute a real container and assert the three
properties that matter (network unreachable, host filesystem invisible,
memory limit kills); they skip — loudly, with the probe's evidence — on
hosts whose runtime cannot run containers (e.g. k8s pods under an AppArmor
``deny mount`` profile). The netns level is asserted for real wherever
`unshare` works, including such pods: kernel-enforced network isolation is
tested against a live listening socket, not against configuration.
"""

import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from causal_data_juicer.runtime.exec_backend import describe, probe, wrap

CAPS = probe()


def _run(argv, timeout=90):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def test_probe_reports_a_level_with_evidence():
    assert CAPS.level in ("container", "netns", "none")
    assert "apparmor" in CAPS.detail
    assert describe(CAPS)


def test_wrap_none_level_is_identity(tmp_path):
    from causal_data_juicer.runtime.exec_backend import Capabilities

    argv = ["echo", "hi"]
    assert wrap(argv, tmp_path, caps=Capabilities("none")) == argv


# -- netns level: runs on this pod and anywhere unshare works ----------------

netns_only = pytest.mark.skipif(
    CAPS.level == "none", reason=f"no isolation available: {CAPS.detail}"
)


@netns_only
def test_network_is_really_unreachable_inside(tmp_path):
    """Bind a live localhost port outside; the wrapped process must fail to
    connect to it — isolation proven against a real socket."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    threading.Thread(target=lambda: srv.accept() if True else None, daemon=True).start()
    try:
        code = (
            f"import socket; s = socket.socket(); s.settimeout(3); "
            f"raise SystemExit(0 if s.connect_ex(('127.0.0.1', {port})) != 0 else 1)"
        )
        probe_argv = [sys.executable, "-c", code]
        assert subprocess.run(probe_argv, check=False).returncode == 1  # reachable outside
        proc = _run(wrap(probe_argv, tmp_path))
        assert proc.returncode == 0, proc.stderr  # unreachable inside
    finally:
        srv.close()


@netns_only
def test_egress_is_blocked_inside(tmp_path):
    code = (
        "import socket; s = socket.socket(); s.settimeout(3); "
        "raise SystemExit(0 if s.connect_ex(('1.1.1.1', 80)) != 0 else 1)"
    )
    proc = _run(wrap([sys.executable, "-c", code], tmp_path))
    assert proc.returncode == 0, proc.stderr


@netns_only
def test_memory_limit_kills_oversized_allocation(tmp_path):
    if CAPS.level == "container":
        pytest.skip("covered by the container-level memory test")
    argv = wrap(
        [sys.executable, "-c", "x = bytearray(1024**3)"],
        tmp_path,
        limits={"as_bytes": 256 * 1024**2},
    )
    proc = _run(argv)
    assert proc.returncode != 0
    argv_ok = wrap(
        [sys.executable, "-c", "x = bytearray(10 * 1024**2)"],
        tmp_path,
        limits={"as_bytes": 512 * 1024**2},
    )
    assert _run(argv_ok).returncode == 0


@netns_only
def test_verifier_output_is_unchanged_by_isolation(tmp_path):
    """Digest safety: wrapping must not alter what the check prints."""
    argv = [sys.executable, "-c", "print('deterministic-output-42')"]
    bare = _run(argv)
    wrapped = _run(wrap(argv, tmp_path))
    assert wrapped.stdout == bare.stdout == "deterministic-output-42\n"


# -- container level: runs wherever a real runtime exists --------------------

container_only = pytest.mark.skipif(
    CAPS.level != "container", reason=f"container runtime unavailable here: {CAPS.detail}"
)


@container_only
def test_container_network_is_off(tmp_path):
    proc = _run(
        wrap(
            [
                "python",
                "-c",
                (
                    "import socket; s = socket.socket(); s.settimeout(3); "
                    "raise SystemExit(0 if s.connect_ex(('1.1.1.1', 80)) != 0 else 1)"
                ),
            ],
            tmp_path,
        )
    )
    assert proc.returncode == 0, proc.stderr


@container_only
def test_container_cannot_see_host_filesystem(tmp_path):
    marker = Path.home() / ".cdj-host-marker"
    marker.write_text("host")
    try:
        proc = _run(
            wrap(
                [
                    "python",
                    "-c",
                    (
                        f"import pathlib; "
                        f"raise SystemExit(1 if pathlib.Path('{marker}').exists() else 0)"
                    ),
                ],
                tmp_path,
            )
        )
        assert proc.returncode == 0, "host filesystem is visible inside the container"
    finally:
        marker.unlink(missing_ok=True)


@container_only
def test_container_memory_limit_enforced(tmp_path):
    proc = _run(
        wrap(
            ["python", "-c", "x = bytearray(2 * 1024**3)"],
            tmp_path,
            limits={"as_bytes": 256 * 1024**2},
        )
    )
    assert proc.returncode != 0


@container_only
def test_container_workspace_is_writable_and_syncs_back(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    proc = _run(wrap(["python", "-c", "open('made-inside.txt', 'w').write('from container')"], ws))
    assert proc.returncode == 0, proc.stderr
    assert (ws / "made-inside.txt").read_text() == "from container"
