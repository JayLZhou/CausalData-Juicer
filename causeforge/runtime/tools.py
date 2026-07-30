"""Tool registry with side-effect grading.

Every tool declares a ``SideEffectClass``.  The executor enforces the
hard rule: in replay mode an ``EXTERNAL_SIDE_EFFECT`` tool is never truly
executed — it is served a dry-run mock, and its observation is normalized
to a constant so determinism digests do not depend on the external world.
"""
from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from causeforge.sdk.schemas import CostLedger, SideEffectClass, ToolCall, digest_of

EXTERNAL_OBS_PLACEHOLDER = "[external-effect]"


@dataclass
class Tool:
    name: str
    side_effect: SideEffectClass
    fn: Callable[..., str]  # fn(workspace: Path, **args) -> observation


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self.tools:
            raise KeyError(f"unknown tool: {name}")
        return self.tools[name]

    def fingerprint(self) -> str:
        return digest_of(sorted((t.name, t.side_effect.value) for t in self.tools.values()))


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, mode: str = "live"):
        assert mode in ("live", "replay")
        self.registry = registry
        self.mode = mode

    def execute(self, workspace: Path, call: ToolCall, ledger: CostLedger) -> tuple[str, str]:
        """Execute a tool call, charge the ledger, return (observation, obs_digest)."""
        tool = self.registry.get(call.tool)
        t0 = time.monotonic()
        if self.mode == "replay" and tool.side_effect == SideEffectClass.EXTERNAL_SIDE_EFFECT:
            obs = f"[dry-run mock] {call.tool} suppressed during replay"
        else:
            obs = tool.fn(workspace, **call.args)
        ledger.charge_tool(time.monotonic() - t0)
        if tool.side_effect == SideEffectClass.EXTERNAL_SIDE_EFFECT:
            norm = EXTERNAL_OBS_PLACEHOLDER
        else:
            norm = obs
        return obs, digest_of({"tool": call.tool, "obs": norm})


# ---------------------------------------------------------------------------
# Built-in tools for the local/python workload family
# ---------------------------------------------------------------------------

def _write_file(workspace: Path, path: str, content: str) -> str:
    target = (workspace / path).resolve()
    if workspace.resolve() not in target.parents and target != workspace.resolve():
        raise ValueError(f"path escapes workspace: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"wrote {path} ({len(content)} chars)"


def _read_file(workspace: Path, path: str) -> str:
    return (workspace / path).read_text()


_PYTEST_SUMMARY = re.compile(r"(\d+) (passed|failed|error)")


def _run_pytest(workspace: Path, timeout: int = 60) -> str:
    from causeforge.runtime.envs import resolve_python

    proc = subprocess.run(
        [resolve_python(workspace), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no",
         "-o", "addopts=", "-o", "testpaths=", "--rootdir=.", "."],
        cwd=workspace, capture_output=True, text=True, timeout=timeout,
    )
    out = proc.stdout + proc.stderr
    counts = {"passed": 0, "failed": 0, "error": 0}
    for n, kind in _PYTEST_SUMMARY.findall(out):
        counts[kind] += int(n)
    # Normalized, time-free summary => deterministic observation digests.
    return f"exit={proc.returncode} passed={counts['passed']} failed={counts['failed'] + counts['error']}"


def _send_report(workspace: Path, message: str) -> str:
    # Stand-in for a real external effect (email/webhook).  Live mode just
    # pretends; the point is the EXTERNAL_SIDE_EFFECT gating during replay.
    return f"report sent: {message[:40]}"


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(Tool("write_file", SideEffectClass.REVERSIBLE, _write_file))
    reg.register(Tool("read_file", SideEffectClass.PURE, _read_file))
    reg.register(Tool("run_pytest", SideEffectClass.IDEMPOTENT, _run_pytest))
    reg.register(Tool("send_report", SideEffectClass.EXTERNAL_SIDE_EFFECT, _send_report))
    return reg
