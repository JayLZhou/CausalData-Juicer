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

from causal_data_juicer.sdk.schemas import CostLedger, Outcome

_SUMMARY = re.compile(r"(\d+) (passed|failed|error)")


class PytestVerifier:
    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def evaluate(self, workspace: Path, ledger: CostLedger) -> Outcome:
        from causal_data_juicer.runtime.envs import resolve_python

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
        argv = resolve_command(self.command, workspace)
        t0 = time.monotonic()
        proc = subprocess.run(argv, cwd=workspace, capture_output=True,
                              text=True, timeout=self.timeout)
        ledger.charge_tool(time.monotonic() - t0)
        out = (proc.stdout + proc.stderr).strip()
        tail = "\n".join(out.splitlines()[-30:])[-3000:]
        success = proc.returncode == 0
        return Outcome(success=success, passed=int(success), failed=int(not success),
                       detail=tail)


def resolve_command(command: list[str], workspace: Path) -> list[str]:
    """Expand {python} to the workspace interpreter; if the executable is
    not on PATH (common in unactivated venvs), fall back to
    `<python> -m <cmd>` so bare "pytest -q" just works."""
    import shutil as _shutil

    from causal_data_juicer.runtime.envs import resolve_python

    python = resolve_python(workspace)
    argv = [a.replace("{python}", python) for a in command]
    head = argv[0]
    if "/" not in head and head != python and _shutil.which(head) is None:
        return [python, "-m", *argv]
    return argv


DEFAULT_SEAL_PATTERNS = ("test_*.py", "*_test.py", "tests/**/*.py", "conftest.py")


class SealedVerifier:
    """Wrap any verifier so protected files (tests, by default) are
    restored from a pristine baseline before every verification — reward
    hacking by editing the check itself becomes impossible, and attempts
    are counted in ``violations``."""

    def __init__(self, inner, baseline_root: Path, patterns=DEFAULT_SEAL_PATTERNS):
        self.inner = inner
        self.patterns = patterns
        self._sealed: dict[str, str] = {}
        root = Path(baseline_root)
        for pattern in patterns:
            for f in root.glob(pattern):
                if f.is_file():
                    self._sealed[str(f.relative_to(root))] = f.read_text()
        self.violations = 0

    def restore(self, workspace: Path) -> int:
        tampered = 0
        for rel, content in self._sealed.items():
            target = Path(workspace) / rel
            if not target.exists() or target.read_text() != content:
                tampered += 1
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
        self.violations += tampered
        return tampered

    def evaluate(self, workspace: Path, ledger: CostLedger) -> Outcome:
        self.restore(workspace)
        return self.inner.evaluate(workspace, ledger)
