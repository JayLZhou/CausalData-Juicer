"""Outcome verifiers — the ground truth for success/failure and flips.

Two built-ins:
- ``PytestVerifier``: parsed pass/fail counts from a workspace test suite;
- ``CommandVerifier``: ANY command, success == exit 0.  This is the
  generality escape hatch: builds, linters, `make test`, `cargo test`,
  SQL runners — every executable workload plugs in through it.

Anything with ``evaluate(workspace, ledger) -> Outcome`` is a verifier;
the collector and replayer only ever see that protocol.
"""
from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from causeforge.sdk.schemas import CostLedger, Outcome

_SUMMARY = re.compile(r"(\d+) (passed|failed|error)")


class PytestVerifier:
    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def evaluate(self, workspace: Path, ledger: CostLedger) -> Outcome:
        from causeforge.runtime.envs import resolve_python

        t0 = time.monotonic()
        proc = subprocess.run(
            [resolve_python(workspace), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=line",
             "-o", "addopts=", "-o", "testpaths=", "--rootdir=.", "."],
            cwd=workspace, capture_output=True, text=True, timeout=self.timeout,
        )
        ledger.charge_tool(time.monotonic() - t0)
        out = proc.stdout + proc.stderr
        counts = {"passed": 0, "failed": 0, "error": 0}
        for n, kind in _SUMMARY.findall(out):
            counts[kind] += int(n)
        failed = counts["failed"] + counts["error"]
        success = proc.returncode == 0 and counts["passed"] > 0
        tail = "\n".join(out.strip().splitlines()[-30:])[-3000:]
        return Outcome(success=success, passed=counts["passed"], failed=failed, detail=tail)


class CommandVerifier:
    """Generic verifier: run ``command`` inside the workspace; success is
    exit code 0.  ``{python}`` in arguments expands to the workspace's
    env-pointer interpreter (falls back to the engine's own)."""

    def __init__(self, command: list[str], timeout: int = 120):
        self.command = list(command)
        self.timeout = timeout

    def evaluate(self, workspace: Path, ledger: CostLedger) -> Outcome:
        from causeforge.runtime.envs import resolve_python

        argv = [a.replace("{python}", resolve_python(workspace)) for a in self.command]
        t0 = time.monotonic()
        proc = subprocess.run(argv, cwd=workspace, capture_output=True,
                              text=True, timeout=self.timeout)
        ledger.charge_tool(time.monotonic() - t0)
        out = (proc.stdout + proc.stderr).strip()
        tail = "\n".join(out.splitlines()[-30:])[-3000:]
        success = proc.returncode == 0
        return Outcome(success=success, passed=int(success), failed=int(not success),
                       detail=tail)
