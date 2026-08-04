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
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_LIMITS = {
    "as_bytes": 4 * 1024**3,  # address space
    "cpu_seconds": 600,
    "fsize_bytes": 1 * 1024**3,  # largest single file a check may write
}


@dataclass
class Capabilities:
    level: str  # container | netns | none
    detail: dict = field(default_factory=dict)


def _apparmor_profile() -> str:
    try:
        return Path("/proc/self/attr/current").read_text().strip()
    except OSError:  # pragma: no cover — no /proc on some platforms
        return "unknown"


def _try(cmd: list[str], timeout: int = 20) -> bool:
    try:
        return (
            subprocess.run(cmd, capture_output=True, timeout=timeout, check=False).returncode == 0
        )
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover — env-dependent
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
        if _try([exe, "run", "--rm", "--network=none", container_image(), "true"], timeout=120):
            detail["runtime"] = runtime  # pragma: no cover — needs a live runtime;
            return Capabilities(
                "container", detail
            )  # pragma: no cover — asserted by test_isolation_backend on capable hosts
        detail[f"{runtime}_error"] = "cannot run containers here (mount ops likely denied)"

    unshare = shutil.which("unshare")
    if unshare and _try([unshare, "-U", "-r", "-n", "true"]):
        detail["unshare"] = unshare
        return Capabilities("netns", detail)

    return Capabilities("none", detail)


_SHIM = "causal_data_juicer.runtime.rlimit_exec"

DEFAULT_IMAGE = "python:3.12-slim"


class IsolationIncompatible(RuntimeError):
    """The command cannot run under the requested isolation level.

    Chiefly: a container mounts only the workspace, so a verify command
    naming a *host* interpreter or script path (what ``resolve_command``
    produces for per-task venvs) does not exist inside the image. Callers
    catch this and downgrade a level, reporting why.
    """


def container_image() -> str:
    return os.environ.get("CDJ_CONTAINER_IMAGE", DEFAULT_IMAGE)


def check_container_compatible(argv: list[str], workspace: Path) -> None:
    """Raise IsolationIncompatible if argv references host paths the
    container will not have."""
    ws = Path(workspace).resolve()
    for a in argv:
        if not a.startswith("/"):
            continue
        p = Path(a)
        if ws == p or ws in p.parents:
            continue  # inside the mounted workspace: fine
        raise IsolationIncompatible(
            f"command references host path {a!r}, which does not exist inside "
            f"the container image ({container_image()}); only {ws} is mounted"
        )


def wrap(
    argv: list[str], workspace: Path, limits: dict | None = None, caps: Capabilities | None = None
) -> list[str]:
    """Rewrite ``argv`` to execute under the strongest available isolation.

    Raises :class:`IsolationIncompatible` at container level when ``argv``
    names host paths the image will not provide.
    """
    caps = caps or probe()
    lim = {**DEFAULT_LIMITS, **(limits or {})}

    if caps.level == "container":
        check_container_compatible(argv, workspace)
        runtime = caps.detail["runtime"]
        ws = str(Path(workspace).resolve())
        return [
            caps.detail[runtime],
            "run",
            "--rm",
            "--network=none",
            "--user",
            "1000:1000",
            "--read-only",
            "--read-only-tmpfs",
            "--memory",
            str(lim["as_bytes"]),
            "--pids-limit",
            "256",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "-v",
            f"{ws}:/ws:rw",
            "-w",
            "/ws",
            container_image(),
            *argv,
        ]

    if caps.level == "netns":
        return [
            caps.detail["unshare"],
            "-U",
            "-r",
            "-n",
            "--",
            sys.executable,
            "-m",
            _SHIM,
            "--as-bytes",
            str(lim["as_bytes"]),
            "--cpu-seconds",
            str(lim["cpu_seconds"]),
            "--fsize-bytes",
            str(lim["fsize_bytes"]),
            "--",
            *argv,
        ]

    return argv


def wrap_or_downgrade(
    argv: list[str], workspace: Path, limits: dict | None = None, caps: Capabilities | None = None
) -> tuple[list[str], Capabilities, str | None]:
    """``wrap`` that degrades instead of failing.

    Returns ``(argv, effective_caps, downgrade_reason)``. A container-level
    host paranoia is not worth a broken run: if the command cannot execute
    inside the image, fall back to the next level and hand the caller the
    reason so it can be printed rather than hidden.
    """
    caps = caps or probe()
    try:
        return wrap(argv, workspace, limits=limits, caps=caps), caps, None
    except IsolationIncompatible as e:
        unshare = shutil.which("unshare")
        lower = (
            Capabilities("netns", {**caps.detail, "unshare": unshare})
            if unshare and _try([unshare, "-U", "-r", "-n", "true"])
            else Capabilities("none", caps.detail)
        )
        return wrap(argv, workspace, limits=limits, caps=lower), lower, str(e)


def describe(caps: Capabilities | None = None) -> str:
    caps = caps or probe()
    if caps.level == "container":
        return (
            f"container isolation via {caps.detail['runtime']} "
            "(no network, read-only rootfs, cgroup limits)"
        )
    if caps.level == "netns":
        return (
            "network-namespace isolation + rlimits (network fully blocked; "
            "NO filesystem isolation — container runtime unavailable: "
            f"apparmor={caps.detail.get('apparmor', '?')})"
        )
    return "NO isolation — plain host execution"
