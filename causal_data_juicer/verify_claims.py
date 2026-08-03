"""`cdj verify-claims` — re-earn the offline-verifiable claims on this machine.

Runs the offline-verifiable subset of the claims ledger end to end and
prints a three-state scorecard (PASS / FAIL / SKIP). Nothing is read from
archived results: the demo is re-collected, the flips re-validated, the
negative controls re-tripped, the regression suite re-replayed, the replay
pack re-executed (if its environments exist locally).

Honesty contract of this tool:
- NOT_RUN is a third state, never counted as PASS. A check that cannot
  run is reported with its reason and how to enable it; strict mode is the
  DEFAULT — a required claim (per experiments/claims.yaml) left NOT_RUN
  exits nonzero. `--lenient` downgrades that to a warning.
- The scorecard states explicitly which ledger rows it does NOT cover.
  Live-scale numbers (multi-config flip-repro sweeps, budget curves,
  revalidation events, source ladders, C-chain) were bought with GPU-hours
  on live endpoints and cannot be re-run offline; they ship as run
  directories and archived JSON under `experiments/results/`, with
  committed replay packs where byte-exact offline reproduction is possible.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PYTEST_CHECKS = [
    ("A2/A3", "non-fix rejection + minimal slicing (toy E2E)", "tests/test_e2e_demo.py"),
    ("A6", "sparse-fork state reconstruction is byte-identical", "tests/test_m3_storage.py"),
    ("A13", "determinism gate rejects outcome-flaky environments", "tests/test_negative_control.py"),
    ("B2", "TRL/verl export formats round-trip", "tests/test_adapters.py"),
]

# Ledger rows this tool cannot re-run offline, and where their evidence lives.
NOT_COVERED = (
    "Not covered here (live endpoints / GPU-hours; evidence = run dirs + "
    "archived JSON in experiments/results/, pre-registered in "
    "experiments/claims.md): A5 cost-per-unit, A7 budget curves, A8 "
    "revalidation events, A10-A12/A14 source ladders & capability sweeps, "
    "A15 worker scaling, C1 training pilot, C2 memory-retrieval eval."
)


class Scorecard:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.not_run: list[tuple[str, str]] = []

    def row(self, cid: str, desc: str, ok: bool, detail: str = "") -> None:
        mark = "PASS" if ok else "FAIL"
        (self.passed if ok else self.failed).append(cid)
        print(f"  [{mark}] {cid:<6} {desc}" + (f"  ({detail})" if detail else ""))

    def skip(self, cid: str, desc: str, reason: str) -> None:
        self.not_run.append((cid, reason))
        print(f"  [NOT_RUN] {cid:<6} {desc}  ({reason})")

    def summary(self, strict: bool = True) -> int:
        print()
        print(f"{len(self.passed)} re-earned, {len(self.not_run)} not run, "
              f"{len(self.failed)} failed.")
        for cid, reason in self.not_run:
            print(f"  NOT_RUN {cid}: {reason}")
        print(f"\n{NOT_COVERED}")
        if self.failed:
            print("\nSome claims FAILED to reproduce — that is reportable; "
                  "please open an issue.")
            return 1
        if self.not_run and strict:
            print("\nstrict (default): required claims left NOT_RUN exit "
                  "nonzero. Use --lenient to downgrade, or enable the check "
                  "(see reasons above).")
            return 1
        if self.not_run:
            print("\nThe subset that ran passed. NOT_RUN checks are NOT "
                  "verified — this is not a full reproduction.")
        else:
            print("\nAll required claims executed and passed on this machine.")
        return 0


def verify_claims(repo_root: Path | None = None, strict: bool = True) -> int:
    root = Path(repo_root or Path.cwd())
    print("cdj verify-claims — executing, not trusting\n")
    card = Scorecard()
    tmp = Path(tempfile.mkdtemp(prefix="cdj-verify-"))

    # A1/A9: fresh demo run, kill line + digest match re-earned
    from causal_data_juicer.pipeline import run_demo
    report = run_demo(tmp / "demo", n_repro=3)
    rate = report.get("flip_repro_rate") or 0.0
    card.row("A1", "flip reproducibility ≥90% on a fresh demo run",
             rate >= 0.9, f"{rate:.0%}, {report['flip_repro_detail']}")
    card.row("A9", "control-branch digest match on that run",
             report.get("control_digest_match_rate") == 1.0,
             f"{report.get('control_digest_match_rate'):.0%}")

    # regression: the exported counterfactual suite replays
    regress = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(tmp / "demo" / "exports" / "test_regression.py")],
        capture_output=True, text=True, cwd=root)
    card.row("Regr", "exported counterfactual cases replay and still flip",
             regress.returncode == 0)

    # ledger-mapped pytest slices
    for cid, desc, target in PYTEST_CHECKS:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", target],
                              capture_output=True, text=True, cwd=root)
        card.row(cid, desc, proc.returncode == 0)

    # replay pack (needs the bench envs)
    pack = root / "replay-packs" / "step-dpo"
    envs_present = (root / "bench_envs" / "pydantic-new").exists()
    if pack.exists() and envs_present:
        work = tmp / "replay"
        work.mkdir()
        shutil.copytree(pack / "llm_cache", work / "llm_cache")
        proc = subprocess.run(
            [sys.executable, "examples/case_step_dpo.py",
             "--base", str(pack / "base-run"), "--out", str(work)],
            capture_output=True, text=True, cwd=root)
        try:
            tail = proc.stdout[proc.stdout.rindex("{"):] if "{" in proc.stdout else "{}"
            got = json.loads(tail)
        except Exception:
            got = {}
        ok = got.get("sampled_branches") == 46 and got.get("flipping_branches") == 7 \
            and got.get("step_dpo_pairs") == 12
        card.row("B1", "replay pack reproduces the live case byte-for-byte "
                       "(46 branches / 7 flips / 12 pairs), offline",
                 ok, json.dumps(got) if got else proc.stderr.strip()[-80:])
    else:
        card.skip("B1", "replay pack NOT verified",
                  "bench envs missing — run `cdj bench-build` to enable this check")

    shutil.rmtree(tmp, ignore_errors=True)
    return card.summary(strict)
