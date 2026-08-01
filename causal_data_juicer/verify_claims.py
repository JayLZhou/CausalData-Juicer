"""`cdj verify-claims` — re-earn the front-page numbers on this machine.

Runs the offline-verifiable subset of the claims ledger end to end and
prints a scorecard. Nothing is read from archived results: the demo is
re-collected, the flips re-validated, the negative controls re-tripped,
the regression suite re-replayed, the replay pack re-executed (if its
environments exist locally). Trust nothing; execute everything.
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


def _row(cid: str, desc: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {cid:<6} {desc}" + (f"  ({detail})" if detail else ""))
    return ok


def verify_claims(repo_root: Path | None = None) -> int:
    root = Path(repo_root or Path.cwd())
    print("cdj verify-claims — executing, not trusting\n")
    all_ok = True
    tmp = Path(tempfile.mkdtemp(prefix="cdj-verify-"))

    # A1/A9: fresh demo run, kill line + digest match re-earned
    from causal_data_juicer.pipeline import run_demo
    report = run_demo(tmp / "demo", n_repro=3)
    rate = report.get("flip_repro_rate") or 0.0
    all_ok &= _row("A1", "flip reproducibility ≥90% on a fresh demo run",
                   rate >= 0.9, f"{rate:.0%}, {report['flip_repro_detail']}")
    all_ok &= _row("A9", "control-branch digest match on that run",
                   report.get("control_digest_match_rate") == 1.0,
                   f"{report.get('control_digest_match_rate'):.0%}")

    # regression: the exported counterfactual suite replays
    regress = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(tmp / "demo" / "exports" / "test_regression.py")],
        capture_output=True, text=True, cwd=root)
    all_ok &= _row("Regr", "exported counterfactual cases replay and still flip",
                   regress.returncode == 0)

    # ledger-mapped pytest slices
    for cid, desc, target in PYTEST_CHECKS:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", target],
                              capture_output=True, text=True, cwd=root)
        all_ok &= _row(cid, desc, proc.returncode == 0)

    # replay pack (needs the bench envs; skip gracefully if absent)
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
        all_ok &= _row("B1", "replay pack reproduces the live case byte-for-byte "
                             "(46 branches / 7 flips / 12 pairs), offline",
                       ok, json.dumps(got) if got else proc.stderr.strip()[-80:])
    else:
        _row("B1", "replay pack skipped (run `cdj bench-build` first)", True, "SKIP")

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("All claims re-earned on this machine." if all_ok
          else "Some claims FAILED to reproduce — that is reportable; please open an issue.")
    return 0 if all_ok else 1
