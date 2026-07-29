"""Outcome verifiers.  M1 ships a pytest verifier: the ground truth for
success/failure and for counterfactual flips."""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

from causeforge.sdk.schemas import CostLedger, Outcome

_SUMMARY = re.compile(r"(\d+) (passed|failed|error)")


class PytestVerifier:
    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def evaluate(self, workspace: Path, ledger: CostLedger) -> Outcome:
        t0 = time.monotonic()
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=line",
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
        tail = "\n".join(out.strip().splitlines()[-6:])
        return Outcome(success=success, passed=counts["passed"], failed=failed, detail=tail)
