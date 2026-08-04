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
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_IMAGE = "python:3.12-slim"
_SHIM = "causal_data_juicer.runtime.rlimit_exec"

DEFAULT_LIMITS = {
    "as_bytes": 4 * 1024**3,  # address space
    "cpu_seconds": 600,
    "fsize_bytes": 1 * 1024**3,  # largest single file a check may write
}


@dataclass
class Capabilities:
    level: str  # container | netns | none
    detail: dict = field(default_factory=dict)


def container_image() -> str:
    return os.environ.get("CDJ_CONTAINER_IMAGE", DEFAULT_IMAGE)


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


def _container_argv(exe: str, workspace: Path, lim: dict) -> list[str]:
    """The container prefix, shared by probe() and wrap() so they can never
    disagree. Only flags supported by BOTH docker and podman are used:
    ``--read-only-tmpfs`` is podman-only (portable form: ``--tmpfs /tmp``),
    and the uid is the caller's, not a hardcoded 1000 — a bind-mounted
    workspace owned by the host user is unwritable to any other uid.
    """
    ws = str(Path(workspace).resolve())
    return [
        exe,
        "run",
        "--rm",
        "--network=none",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--read-only",
        "--tmpfs",
        "/tmp",
        "--memory",
        str(lim["as_bytes"]),
        "--pids-limit",
        "256",
        "--security-opt",
        "no-new-privileges",
        "--cap-drop",
        "ALL",
        "-e",
        "HOME=/tmp",  # read-only rootfs: give tools a writable HOME
        "-v",
        f"{ws}:/ws:rw",
        "-w",
        "/ws",
        container_image(),
    ]


def _probe_container(exe: str) -> str | None:
    """Run a throwaway container with **the exact flag set wrap() emits**.

    Probing with a simplified command was a real defect: podman-only flags
    (`--read-only-tmpfs`) and a hardcoded `--user 1000:1000` passed the
    simple probe and then broke every real invocation on Docker hosts. The
    probe now fails for the same reasons a real run would, so an
    unsupported flag downgrades the level instead of producing broken
    commands.
    """
    with tempfile.TemporaryDirectory(prefix="cdj-probe-") as tmp:
        argv = [
            *_container_argv(exe, Path(tmp), DEFAULT_LIMITS),
            "python",
            "-c",
            "open('probe.txt', 'w').write('ok')",  # also proves the mount is writable
        ]
        try:
            proc = subprocess.run(argv, capture_output=True, timeout=300, check=False, text=True)
        except (OSError, subprocess.TimeoutExpired) as e:  # pragma: no cover — env-dependent
            return f"{type(e).__name__}: {e}"
        if proc.returncode != 0:
            return (
                (proc.stderr or proc.stdout).strip().splitlines()[-1][:200]
                if (proc.stderr or proc.stdout).strip()
                else f"exit {proc.returncode}"
            )
        if not (Path(tmp) / "probe.txt").exists():
            return "container ran but the workspace mount was not writable"
    return None


@functools.lru_cache(maxsize=1)
def probe() -> Capabilities:
    detail = {"apparmor": _apparmor_profile()}

    for runtime in ("podman", "docker"):
        exe = shutil.which(runtime)
        if not exe:
            continue
        detail[runtime] = exe
        error = _probe_container(exe)
        if error is None:
            detail["runtime"] = runtime
            return Capabilities("container", detail)
        detail[f"{runtime}_error"] = error

    unshare = shutil.which("unshare")
    if unshare and _try([unshare, "-U", "-r", "-n", "true"]):
        detail["unshare"] = unshare
        return Capabilities("netns", detail)

    return Capabilities("none", detail)


class IsolationIncompatible(RuntimeError):
    """The command cannot run under the requested isolation level.

    Chiefly: a container mounts only the workspace, so a verify command
    naming a *host* interpreter or script path (what ``resolve_command``
    produces for per-task venvs) does not exist inside the image. Callers
    catch this and downgrade a level, reporting why.
    """


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
        return [*_container_argv(caps.detail[caps.detail["runtime"]], workspace, lim), *argv]

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
