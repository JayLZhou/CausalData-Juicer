"""CauseForge CLI.

    causeforge demo   [--out runs/demo] [--repro 3]   one-command E2E demo
    causeforge report [run_dir]                        re-print a run report
    causeforge regress [run_dir]                       run exported counterfactual regression tests
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _print_report(report: dict) -> None:
    print("=" * 62)
    print("CauseForge run report")
    print("=" * 62)
    rate = report.get("flip_repro_rate")
    print(f"episodes            : {report['episodes']} "
          f"({report['failed_episodes']} failed)")
    print(f"candidates screened : {report['candidates_screened']}")
    print(f"units by tier       : {report['units_by_tier']}")
    print(f"determinism control : {'OK' if report['determinism_control_ok'] else 'MISMATCH'}")
    print(f"FLIP REPRO RATE     : {rate if rate is None else f'{rate:.1%}'} "
          f"({report['flip_repro_detail']})  [kill line: >= 90%]")
    sl = report["slicing"]
    print(f"causal slicing      : {sl['atoms_before']} atoms -> {sl['atoms_after']} atoms")
    c = report["cost"]
    print(f"cost ledger         : {c['llm_calls']} llm calls, "
          f"{c['tokens_in']}+{c['tokens_out']} tokens, "
          f"{c['tool_calls']} tool calls, {c['replay_runs']} replays, "
          f"{c['wall_time_s']}s tool-time, ${c['dollars']:.2f}")
    print(f"cost/validated unit : {report['cost_per_validated_unit_s']}s")
    print("exports:")
    for name, path in report["exports"].items():
        n = sum(1 for _ in open(path)) if Path(path).exists() else 0
        print(f"  {name:<10} {n:>3} rows  {path}")
    print(f"total wall time     : {report['wall_time_total_s']}s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="causeforge")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo", help="run the end-to-end toy demo")
    p_demo.add_argument("--out", default="runs/demo")
    p_demo.add_argument("--repro", type=int, default=3)
    p_demo.add_argument("--keep-workspaces", action="store_true")

    p_report = sub.add_parser("report", help="print a saved run report")
    p_report.add_argument("run_dir", nargs="?", default="runs/demo")

    p_regress = sub.add_parser("regress", help="run exported regression tests")
    p_regress.add_argument("run_dir", nargs="?", default="runs/demo")

    args = parser.parse_args(argv)

    if args.cmd == "demo":
        from causeforge.pipeline import run_demo
        report = run_demo(Path(args.out), n_repro=args.repro,
                          keep_workspaces=args.keep_workspaces)
        _print_report(report)
        rate = report.get("flip_repro_rate")
        return 0 if (rate is not None and rate >= 0.9) else 1

    if args.cmd == "report":
        report = json.loads((Path(args.run_dir) / "report.json").read_text())
        _print_report(report)
        return 0

    if args.cmd == "regress":
        test_file = Path(args.run_dir) / "exports" / "test_regression.py"
        if not test_file.exists():
            print(f"no regression export at {test_file}", file=sys.stderr)
            return 2
        return subprocess.call([sys.executable, "-m", "pytest", "-q", str(test_file)])

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
