"""Dependency-migration bench task model (spec: docs/bench-m15-spec.md).

A task is a small repo written against an *old* major version of one
dependency family, executed in an environment that has the *new* version
installed — so its tests fail until the agent migrates the source.
Tests are sealed: the verifier refuses success if they were touched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from causeforge.runtime.envs import TaskEnv
from causeforge.sdk.schemas import digest_of

WORKLOAD_ID = "depmig-v1"


@dataclass
class Family:
    name: str
    old_pins: list[str]
    new_pins: list[str]
    base_python: str | None = None  # None -> engine's interpreter

    def old_env(self) -> TaskEnv:
        return TaskEnv(name=f"{self.name}-old", packages=self.old_pins,
                       **({"base_python": self.base_python} if self.base_python else {}))

    def new_env(self) -> TaskEnv:
        return TaskEnv(name=f"{self.name}-new", packages=self.new_pins,
                       **({"base_python": self.base_python} if self.base_python else {}))


@dataclass
class DepMigTask:
    id: str
    family: Family
    tier: int  # 1 mechanical | 2 multi-point/structural | 3 silent semantic
    description: str
    files: dict[str, str]  # sources + sealed tests (test_*.py)
    migration_points: list[str] = field(default_factory=list)

    def setup(self, workspace: Path) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        for rel, content in self.files.items():
            p = workspace / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)

    def test_files(self) -> dict[str, str]:
        return {k: v for k, v in self.files.items() if Path(k).name.startswith("test_")}

    def tests_digest(self) -> str:
        return digest_of(self.test_files())

    def agent_prompt(self) -> str:
        deps = ", ".join(self.family.new_pins)
        return (
            f"{self.description}\n"
            f"This project was written for an older major version of its dependency; "
            f"the environment now has {deps} installed, so the tests currently fail. "
            f"Migrate the SOURCE files so the tests pass. Do not modify test files, "
            f"do not change installed packages. Source files: "
            + ", ".join(sorted(k for k in self.files if not Path(k).name.startswith("test_")))
        )


# Hermeticity: substrings forbidden in sealed test files (spec §4).
FORBIDDEN_IN_TESTS = [
    "import socket", "import requests", "import httpx", "urllib",
    "time.time(", "datetime.now(", "datetime.utcnow(", "random.random(",
]


def scan_hermeticity(task: DepMigTask) -> list[str]:
    violations = []
    for name, content in task.test_files().items():
        for pattern in FORBIDDEN_IN_TESTS:
            if pattern in content:
                violations.append(f"{task.id}:{name}: forbidden '{pattern}'")
    return violations
