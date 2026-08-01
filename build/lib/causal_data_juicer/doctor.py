"""`cdj doctor` — zero-config environment check.

A new user should know within seconds whether this machine can run the
demo, and whether their LLM endpoint is reachable, before anything else.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

OK, BAD, WARN = "✓", "✗", "!"


def _check(label: str, ok: bool, hint: str = "", warn: bool = False) -> bool:
    mark = OK if ok else (WARN if warn else BAD)
    line = f"  {mark} {label}"
    if not ok and hint:
        line += f"\n      ↳ {hint}"
    print(line)
    return ok or warn


def run_doctor(base_url: str | None = None) -> int:
    print("cdj doctor\n")
    good = True

    v = sys.version_info
    good &= _check(f"python {v.major}.{v.minor}.{v.micro} (need ≥3.11)", v >= (3, 11),
                   "install Python 3.11+ and recreate the venv")

    try:
        import pydantic
        good &= _check(f"pydantic {pydantic.VERSION}", True)
    except ImportError:
        good &= _check("pydantic", False, "pip install -e .")

    good &= _check("pytest on PATH (verifier)",
                   subprocess.run([sys.executable, "-m", "pytest", "--version"],
                                  capture_output=True).returncode == 0,
                   "pip install pytest")

    try:
        import pyarrow  # noqa: F401
        _check("pyarrow (verl parquet export)", True)
    except ImportError:
        _check("pyarrow missing — verl export falls back to JSONL", True, warn=True)

    tmp = Path(tempfile.mkdtemp(prefix="cdj-doctor-"))
    writable = tmp.exists()
    shutil.rmtree(tmp, ignore_errors=True)
    good &= _check("scratch space writable", writable)

    if base_url:
        try:
            with urllib.request.urlopen(f"{base_url.rstrip('/')}/models", timeout=5) as r:
                models = [m.get("id") for m in json.loads(r.read()).get("data", [])][:3]
            good &= _check(f"endpoint {base_url} reachable (models: {', '.join(map(str, models))})", True)
        except Exception as e:
            good &= _check(f"endpoint {base_url}", False,
                           f"unreachable ({type(e).__name__}) — live collection needs an "
                           f"OpenAI-compatible endpoint; the offline demo works without one")
    else:
        _check("no --base-url given — skipped endpoint check (offline demo needs none)",
               True, warn=True)

    print()
    if good:
        print("All good. Next: `cdj demo` (offline, ~20s) or the tutorial in docs/tutorial.md")
        return 0
    print("Fix the ✗ items above, then re-run `cdj doctor`.")
    return 1
