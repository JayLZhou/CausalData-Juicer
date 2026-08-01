"""YAML recipe runner — `cdj process --config recipe.yaml`.

A recipe is Data-Juicer's UX on the interventional algebra:

    workdir: runs/recipe-demo
    process:
      - collect_toy: {}
      - screen_failures: {}
      - paired_replay: {n_repro: 3}
      - minimize: {}
      - export_views: {}
      - save_run: {}
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import yaml

from causal_data_juicer.ops import ops_zoo  # noqa: F401 — populates the registry
from causal_data_juicer.ops.base_op import OPERATORS, OpContext


def run_recipe(config_path: Path) -> OpContext:
    config = yaml.safe_load(Path(config_path).read_text())
    workdir = Path(config.get("workdir", "runs/recipe"))
    if config.get("fresh", True) and workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    ctx = OpContext(workdir=workdir)
    ctx.meta["recipe"] = str(config_path)
    steps = config.get("process", [])
    print(f"recipe {config_path} — {len(steps)} ops → {workdir}")
    for step in steps:
        (name, params), = step.items() if isinstance(step, dict) else ((step, {}),)
        op = OPERATORS.get(name)(**(params or {}))
        t0 = time.monotonic()
        ctx = op.run(ctx)
        print(f"  [{op.category:<14}] {name:<18} {time.monotonic()-t0:6.1f}s  "
              f"{op.summary(ctx)}")
    shutil.rmtree(workdir / "scratch", ignore_errors=True)
    return ctx


def list_ops(category: str | None = None) -> str:
    rows = []
    for name, cls in OPERATORS.items():
        if category and cls.category != category:
            continue
        doc = (cls.__doc__ or "").strip().split("\n")[0]
        rows.append(f"  {cls.category:<14} {name:<18} {doc}")
    return "operator zoo:\n" + "\n".join(rows)
