"""Execution isolation for verify commands, at the strongest level the host
actually supports — probed, never assumed.

Levels (best first):
- ``container``  — rootless Podman/Docker: mount+net+pid namespaces, no
  network, read-only rootfs, cgroup resource limits. Requires a runtime
  that can create mounts (blocked on some hardened k8s pods by an AppArmor
  ``deny mount`` profile, e.g. ``cri-containerd.apparmor.d``).
- ``netns``      — user+network namespace (`unshare -U -r -n`) plus
  RLIMIT_AS/CPU/FSIZE via an exec shim. Network isolation here is
  kernel-enforced and real (even localhost is unreachable); filesystem
  isolation is NOT provided — the path choke point and workspace copies
  remain the only fs guards.
- ``none``       — plain host execution.

`probe()` reports the level with evidence; `wrap()` rewrites an argv to run
under that level. The probe result is cached per process.
"""
from __future__ import annotations

import functools
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_LIMITS = {
    "as_bytes": 4 * 1024**3,     # address space
    "cpu_seconds": 600,
    "fsize_bytes": 1 * 1024**3,  # largest single file a check may write
}


@dataclass
class Capabilities:
    level: str                      # container | netns | none
    detail: dict = field(default_factory=dict)


def _apparmor_profile() -> str:
    try:
        return Path("/proc/self/attr/current").read_text().strip()
    except OSError:
        return "unknown"


def _try(cmd: list[str], timeout: int = 20) -> bool:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@functools.lru_cache(maxsize=1)
def probe() -> Capabilities:
    detail = {"apparmor": _apparmor_profile()}

    for runtime in ("podman", "docker"):
        exe = shutil.which(runtime)
        if not exe:
            continue
        detail[runtime] = exe
        # the decisive test is running a real container, not --version
        if _try([exe, "run", "--rm", "--network=none", "alpine", "true"], timeout=60):
            detail["runtime"] = runtime
            return Capabilities("container", detail)
        detail[f"{runtime}_error"] = "cannot run containers here (mount ops likely denied)"

    unshare = shutil.which("unshare")
    if unshare and _try([unshare, "-U", "-r", "-n", "true"]):
        detail["unshare"] = unshare
        return Capabilities("netns", detail)

    return Capabilities("none", detail)


_SHIM = "causal_data_juicer.runtime.rlimit_exec"


def wrap(argv: list[str], workspace: Path, limits: dict | None = None,
         caps: Capabilities | None = None) -> list[str]:
    """Rewrite ``argv`` to execute under the strongest available isolation."""
    caps = caps or probe()
    lim = {**DEFAULT_LIMITS, **(limits or {})}

    if caps.level == "container":
        runtime = caps.detail["runtime"]
        ws = str(Path(workspace).resolve())
        return [
            caps.detail[runtime], "run", "--rm",
            "--network=none",
            "--user", "1000:1000",
            "--read-only", "--read-only-tmpfs",
            "--memory", str(lim["as_bytes"]),
            "--pids-limit", "256",
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",
            "-v", f"{ws}:/ws:rw", "-w", "/ws",
            "python:3.12-slim",
        ] + argv

    if caps.level == "netns":
        return [
            caps.detail["unshare"], "-U", "-r", "-n", "--",
            sys.executable, "-m", _SHIM,
            "--as-bytes", str(lim["as_bytes"]),
            "--cpu-seconds", str(lim["cpu_seconds"]),
            "--fsize-bytes", str(lim["fsize_bytes"]),
            "--",
        ] + argv

    return argv


def describe(caps: Capabilities | None = None) -> str:
    caps = caps or probe()
    if caps.level == "container":
        return (f"container isolation via {caps.detail['runtime']} "
                "(no network, read-only rootfs, cgroup limits)")
    if caps.level == "netns":
        return ("network-namespace isolation + rlimits (network fully blocked; "
                "NO filesystem isolation — container runtime unavailable: "
                f"apparmor={caps.detail.get('apparmor', '?')})")
    return "NO isolation — plain host execution"
