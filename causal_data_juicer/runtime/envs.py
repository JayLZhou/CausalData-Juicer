"""Per-task virtualenv isolation (Docker-less fallback, see bench spec §4).

A ``TaskEnv`` pins a package set on a base interpreter.  ``EnvManager``
builds each env exactly once (network allowed at build time only) and
freezes its package list for provenance.  Envs live *outside* any
workspace and are treated as immutable afterwards; a workspace carries
only a tiny pointer file (``.causeforge_env.json``) that snapshots and
replays travel with.  ``resolve_python`` is how run_pytest / the verifier
pick the right interpreter for a workspace.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# On-disk data contract — predates the rebrand; never rename.
ENV_POINTER = ".causeforge_env.json"


@dataclass
class TaskEnv:
    name: str
    packages: list[str] = field(default_factory=list)  # "pkg==x.y.z" pins
    base_python: str = sys.executable

    def key(self) -> str:
        return self.name


class EnvManager:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()  # pointers must survive any cwd
        self.root.mkdir(parents=True, exist_ok=True)

    def _python_of(self, env_dir: Path) -> Path:
        return env_dir / "bin" / "python"

    def ensure(self, env: TaskEnv) -> Path:
        """Create the env if missing; return its interpreter path."""
        env_dir = self.root / env.key()
        marker = env_dir / ".causeforge_ready.json"
        python = self._python_of(env_dir)
        if marker.exists():
            return python
        subprocess.run([env.base_python, "-m", "venv", str(env_dir)], check=True)
        pkgs = ["pytest>=8", *env.packages]  # verifier runs inside the env
        subprocess.run(
            [str(python), "-m", "pip", "install", "-q", *pkgs],
            check=True,
        )
        freeze = subprocess.run(
            [str(python), "-m", "pip", "freeze"], capture_output=True, text=True, check=True
        ).stdout
        marker.write_text(
            json.dumps(
                {
                    "name": env.name,
                    "requested": env.packages,
                    "frozen": sorted(freeze.strip().splitlines()),
                    "base_python": env.base_python,
                },
                indent=2,
            )
        )
        return python

    def provenance(self, env: TaskEnv) -> dict:
        marker = self.root / env.key() / ".causeforge_ready.json"
        return json.loads(marker.read_text()) if marker.exists() else {}


def write_env_pointer(
    workspace: Path, python: Path, name: str | None = None, pins: list[str] | None = None
) -> None:
    """Pointer v2 carries the env *identity* (name + pins), not just an
    absolute path, so snapshots stay replayable across machines and
    directory renames."""
    payload: dict[str, str | list[str]] = {"python": str(python)}
    if name:
        payload["env_name"] = name
    if pins:
        payload["pins"] = pins
    (Path(workspace) / ENV_POINTER).write_text(json.dumps(payload) + "\n")


def resolve_python(workspace: Path) -> str:
    """Interpreter for this workspace, via a fallback chain:
    recorded path -> local env of the same name -> auto-build (only if
    CDJ_BUILD_ENVS=1) -> the engine's interpreter, loudly."""
    import os
    import warnings

    pointer = Path(workspace) / ENV_POINTER
    if not pointer.exists():
        return sys.executable
    data = json.loads(pointer.read_text())
    recorded = data.get("python", sys.executable)
    if Path(recorded).exists():
        return recorded
    name = data.get("env_name")
    if name:
        for root in (Path.cwd() / "bench_envs", Path(__file__).resolve().parents[2] / "bench_envs"):
            local = root / name / "bin" / "python"
            if local.exists():
                return str(local)
        if data.get("pins") and os.environ.get("CDJ_BUILD_ENVS") == "1":
            python = EnvManager(Path.cwd() / "bench_envs").ensure(
                TaskEnv(name=name, packages=list(data["pins"]))
            )
            return str(python)
    warnings.warn(
        f"env pointer '{recorded}' is stale and no local env "
        f"matches{' ' + repr(name) if name else ''}; falling back to "
        f"{sys.executable} (set CDJ_BUILD_ENVS=1 to rebuild pinned envs)",
        stacklevel=2,
    )
    return sys.executable
