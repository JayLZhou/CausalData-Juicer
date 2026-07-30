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
    det = report["determinism_control_ok"]
    print(f"determinism control : {'n/a' if det is None else 'OK' if det else 'MISMATCH'}"
          + (f"  (digest match {report['control_digest_match_rate']:.1%})"
             if report.get("control_digest_match_rate") is not None else ""))
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

    p_exp = sub.add_parser("export", help="export a run to a training-stack format")
    p_exp.add_argument("--run", default="runs/depmig-7b")
    p_exp.add_argument("--format", choices=["trl-sft", "trl-dpo", "verl"], required=True)
    p_exp.add_argument("--out", default=None)

    p_acq = sub.add_parser("acquire-eval", help="M2: cost-per-unit curves across policies")
    p_acq.add_argument("--base", default="runs/depmig-7b")
    p_acq.add_argument("--pool", nargs="*", default=[])
    p_acq.add_argument("--policies", default="exhaustive,random:0,random:1,adaptive")
    p_acq.add_argument("--budgets", default="15,30,60,120")
    p_acq.add_argument("--repro", type=int, default=3)
    p_acq.add_argument("--out", default="experiments/results/m2_curves.json")

    p_bench = sub.add_parser("bench-build", help="build + validate the depmig bench")
    p_bench.add_argument("--env-root", default="bench_envs")
    p_bench.add_argument("--out", default="bench_envs/certificate.json")

    p_live = sub.add_parser("collect-depmig", help="live collection on the depmig bench")
    p_live.add_argument("--base-url", default="http://127.0.0.1:8010/v1")
    p_live.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    p_live.add_argument("--out", default="runs/depmig")
    p_live.add_argument("--repro", type=int, default=3)
    p_live.add_argument("--max-steps", type=int, default=10)
    p_live.add_argument("--env-root", default="bench_envs")
    p_live.add_argument("--fixer-candidates", type=int, default=1)
    p_live.add_argument("--fixer-base-url", default=None)
    p_live.add_argument("--fixer-model", default=None)
    p_live.add_argument("--llm-cache", default=None, help="shared cache dir (reuse across runs)")
    p_live.add_argument("--tasks", nargs="*", default=None, help="subset of task ids")

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

    if args.cmd == "export":
        from causeforge.compiler.adapters import ADAPTERS
        from causeforge.run_store import RunStore
        store = RunStore(Path(args.run))
        suffix = "" if args.format == "verl" else ".jsonl"
        out = Path(args.out) if args.out else Path(args.run) / "exports" / f"{args.format}{suffix}"
        path = ADAPTERS[args.format](store.load_units(), store.load_episodes(), out)
        n = sum(1 for _ in open(path, "rb"))
        print(f"{args.format}: {path} ({'parquet' if path.suffix == '.parquet' else f'{n} rows'})")
        return 0

    if args.cmd == "acquire-eval":
        from causeforge.acquisition.evaluate import evaluate, print_eval
        report = evaluate(
            Path(args.base), [Path(p) for p in args.pool],
            policies=args.policies.split(","),
            budgets=[int(b) for b in args.budgets.split(",")],
            n_repro=args.repro,
        )
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2))
        print_eval(report)
        print(f"curves: {out}")
        return 0

    if args.cmd == "bench-build":
        import tempfile

        from causeforge.workloads.depmig.build import (
            build_and_validate,
            print_certificate,
            save_certificate,
        )
        with tempfile.TemporaryDirectory(prefix="cf-bench-") as scratch:
            cert = build_and_validate(Path(args.env_root), Path(scratch))
        save_certificate(cert, Path(args.out))
        print_certificate(cert)
        print(f"certificate: {args.out}")
        return 0 if cert["valid"] else 1

    if args.cmd == "collect-depmig":
        from causeforge.pipeline_depmig import run_depmig
        report = run_depmig(
            Path(args.out), base_url=args.base_url, model=args.model,
            n_repro=args.repro, max_steps=args.max_steps,
            task_ids=args.tasks, env_root=Path(args.env_root),
            fixer_candidates=args.fixer_candidates,
            fixer_base_url=args.fixer_base_url, fixer_model=args.fixer_model,
            llm_cache=Path(args.llm_cache) if args.llm_cache else None,
        )
        _print_report(report)
        extra = (f"agent solved       : {report['agent_solved']}/{report['episodes']} "
                 f"(seal violations: {report['seal_violations']})")
        print(extra)
        for key in sorted(report["breakdown"]):
            b = report["breakdown"][key]
            print(f"  {key:<18} candidates={b['candidates']} flipped={b['flipped']} "
                  f"repro={b['repro_flips']}/{b['repro_runs']}")
        rate = report.get("flip_repro_rate")
        return 0 if (rate is None or rate >= 0.9) else 1

    if args.cmd == "regress":
        test_file = Path(args.run_dir) / "exports" / "test_regression.py"
        if not test_file.exists():
            print(f"no regression export at {test_file}", file=sys.stderr)
            return 2
        return subprocess.call([sys.executable, "-m", "pytest", "-q", str(test_file)])

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
