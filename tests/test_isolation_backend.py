"""The isolation backend must be *proven*, not configured.

Each level's tests run only at that level, and each asserts the same
properties by execution: network unreachable (against a live socket),
resource limit enforced, verifier output byte-unchanged. Container tests
additionally assert the host filesystem is invisible.

Gating history: an earlier version gated the netns tests on "level is not
none", so on a container-capable host they ran through the container wrap
carrying a *host* interpreter path that does not exist inside the image —
three spurious failures, and a real product bug behind them (now
`check_container_compatible` / `wrap_or_downgrade`).
"""

import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from causal_data_juicer.runtime.exec_backend import (
    Capabilities,
    IsolationIncompatible,
    check_container_compatible,
    container_image,
    describe,
    memory_hog_code,
    probe,
    wrap,
    wrap_or_downgrade,
)

CAPS = probe()

netns_only = pytest.mark.skipif(
    CAPS.level != "netns", reason=f"level is {CAPS.level}, not netns: {CAPS.detail}"
)
container_only = pytest.mark.skipif(
    CAPS.level != "container", reason=f"container runtime unavailable here: {CAPS.detail}"
)


def _run(argv, timeout=120):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def _live_port():
    """A bound, listening localhost port that a wrapped process must not reach."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    threading.Thread(target=srv.accept, daemon=True).start()
    return srv, srv.getsockname()[1]


def _unreachable_probe(port: int) -> str:
    return (
        f"import socket; s = socket.socket(); s.settimeout(3); "
        f"raise SystemExit(0 if s.connect_ex(('127.0.0.1', {port})) != 0 else 1)"
    )


EGRESS_PROBE = (
    "import socket; s = socket.socket(); s.settimeout(3); "
    "raise SystemExit(0 if s.connect_ex(('1.1.1.1', 80)) != 0 else 1)"
)


# -- level-agnostic contracts ------------------------------------------------


def test_probe_reports_a_level_with_evidence():
    assert CAPS.level in ("container", "netns", "none")
    assert "apparmor" in CAPS.detail
    assert describe(CAPS)


def test_container_level_is_reached_where_it_is_required():
    """CI sets CDJ_REQUIRE_CONTAINER=1 on hosts that ship a runtime, so a
    broken container path fails loudly instead of quietly skipping every
    container test — the SKIP-as-PASS trap, one level down."""
    if os.environ.get("CDJ_REQUIRE_CONTAINER") != "1":
        pytest.skip("container level not required on this host")
    assert CAPS.level == "container", (
        f"CDJ_REQUIRE_CONTAINER=1 but probe fell back to {CAPS.level}: {CAPS.detail}"
    )


def test_wrap_none_level_is_identity(tmp_path):
    argv = ["echo", "hi"]
    assert wrap(argv, tmp_path, caps=Capabilities("none")) == argv


def test_container_rejects_host_paths_it_cannot_provide(tmp_path):
    """The bug that broke container hosts: resolve_command hands us a host
    interpreter path, and the container mounts only the workspace."""
    caps = Capabilities("container", {"runtime": "podman", "podman": "/usr/bin/podman"})
    with pytest.raises(IsolationIncompatible):
        wrap(["/opt/venvs/task/bin/python", "-m", "pytest"], tmp_path, caps=caps)
    wrap(["pytest", "-q"], tmp_path, caps=caps)  # PATH lookup inside the image: fine
    check_container_compatible([str(tmp_path / "bin" / "python")], tmp_path)  # mounted: fine


def test_downgrade_reports_reason_instead_of_breaking(tmp_path):
    caps = Capabilities("container", {"runtime": "podman", "podman": "/usr/bin/podman"})
    argv, eff, reason = wrap_or_downgrade(
        ["/opt/venvs/task/bin/python", "-c", "pass"], tmp_path, caps=caps
    )
    assert eff.level in ("netns", "none")
    assert reason and "does not exist inside" in reason
    assert "/opt/venvs/task/bin/python" in argv  # still runs, just less isolated


def test_container_image_is_configurable(monkeypatch):
    monkeypatch.setenv("CDJ_CONTAINER_IMAGE", "my/custom:tag")
    assert container_image() == "my/custom:tag"


# -- netns level -------------------------------------------------------------


@netns_only
def test_netns_cannot_reach_a_live_local_socket(tmp_path):
    srv, port = _live_port()
    try:
        argv = [sys.executable, "-c", _unreachable_probe(port)]
        assert _run(argv).returncode == 1  # reachable outside the wrapper
        assert _run(wrap(argv, tmp_path)).returncode == 0  # unreachable inside
    finally:
        srv.close()


@netns_only
def test_netns_blocks_egress(tmp_path):
    assert _run(wrap([sys.executable, "-c", EGRESS_PROBE], tmp_path)).returncode == 0


@netns_only
def test_netns_memory_limit_kills_oversized_allocation(tmp_path):
    limit = 256 * 1024**2
    over = wrap(
        [sys.executable, "-c", memory_hog_code(4 * limit)], tmp_path, limits={"as_bytes": limit}
    )
    assert _run(over).returncode != 0
    under = wrap(
        [sys.executable, "-c", memory_hog_code(16 * 1024**2)],
        tmp_path,
        limits={"as_bytes": 512 * 1024**2},
    )
    assert _run(under).returncode == 0


@netns_only
def test_netns_leaves_verifier_output_byte_identical(tmp_path):
    argv = [sys.executable, "-c", "print('deterministic-output-42')"]
    assert _run(wrap(argv, tmp_path)).stdout == _run(argv).stdout == "deterministic-output-42\n"


# -- container level ---------------------------------------------------------


@container_only
def test_container_cannot_reach_a_live_local_socket(tmp_path):
    srv, port = _live_port()
    try:
        proc = _run(wrap(["python", "-c", _unreachable_probe(port)], tmp_path))
        assert proc.returncode == 0, proc.stderr
    finally:
        srv.close()


@container_only
def test_container_blocks_egress(tmp_path):
    proc = _run(wrap(["python", "-c", EGRESS_PROBE], tmp_path))
    assert proc.returncode == 0, proc.stderr


@container_only
def test_container_cannot_see_host_filesystem(tmp_path):
    marker = Path.home() / ".cdj-host-marker"
    marker.write_text("host")
    try:
        code = f"import pathlib; raise SystemExit(1 if pathlib.Path('{marker}').exists() else 0)"
        proc = _run(wrap(["python", "-c", code], tmp_path))
        assert proc.returncode == 0, "host filesystem is visible inside the container"
    finally:
        marker.unlink(missing_ok=True)


@container_only
def test_container_memory_claim_matches_reality(tmp_path):
    """cgroups cap *resident* memory, so the old probe — a lazily-mapped
    `bytearray(2GB)` — sailed past a 256MB limit and exited 0. Touch every
    page, and assert the engine only advertises the limit when this host
    actually enforces it (Docker silently ignores --memory when the cgroup
    memory controller is unavailable)."""
    limit = 256 * 1024**2
    proc = _run(
        wrap(
            ["python", "-c", memory_hog_code(4 * limit)],
            tmp_path,
            limits={"as_bytes": limit},
        )
    )
    killed = proc.returncode != 0
    assert killed == bool(CAPS.detail.get("memory_limit_enforced")), (
        f"probe said memory_limit_enforced="
        f"{CAPS.detail.get('memory_limit_enforced')}, observed killed={killed}"
    )
    if not killed:  # the engine must not claim what it cannot do
        assert "WITHOUT enforced memory limits" in describe(CAPS)


@container_only
def test_container_leaves_verifier_output_byte_identical(tmp_path):
    argv = ["python", "-c", "print('deterministic-output-42')"]
    assert _run(wrap(argv, tmp_path)).stdout == "deterministic-output-42\n"


@container_only
def test_container_workspace_is_writable_and_syncs_back(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    proc = _run(wrap(["python", "-c", "open('made-inside.txt', 'w').write('from container')"], ws))
    assert proc.returncode == 0, proc.stderr
    assert (ws / "made-inside.txt").read_text() == "from container"
