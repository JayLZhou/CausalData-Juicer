"""C1 (RQ1) data preparation: does replay-VALIDATED data beat zero-cost
unvalidated proposals from the same distribution, token for token?

Arms (identical rendering, matched token budgets, same source models):
  validated   SFT rows from units that flipped and reproduced (the only
              thing the replay engine adds is this certificate)
  suggested   SFT rows from unvalidated candidate proposals (what you
              get for free if you skip replay: plausible fixes, some
              right, some wrong — nobody checked)

Split: train on {pydantic, numpy, click, pandas}; hold out
{sqlalchemy, networkx} for cross-family agent evaluation.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from causal_data_juicer.compiler.common import render_context
from causal_data_juicer.interventions.apply import apply_intervention
from causal_data_juicer.run_store import RunStore
from causal_data_juicer.sdk.schemas import EvidenceTier

RUNS = ["depmig-7b", "depmig-7b-fixer14b", "depmig-7b-pandas", "depmig-7b-pandas-f14b",
        "depmig-14b", "depmig-7b-ext", "depmig-7b-ext-f14b", "depmig-full-pool",
        "depmig-fixer-tests", "depmig-refine", "depmig-kitchen-sink"]
TRAIN_FAMILIES = {"p": "pydantic", "n": "numpy", "c": "click", "d": "pandas"}
OUT = Path("experiments/c1_data")


def rows_from_runs():
    validated, suggested, seen = [], [], set()
    for run in RUNS:
        store = RunStore(Path("runs") / run)
        episodes = {ep.id: ep for ep in store.load_episodes()}
        for unit in store.load_units():
            ep = episodes.get(unit.episode_id)
            if ep is None or unit.task_id[0] not in TRAIN_FAMILIES:
                continue
            iv = unit.effective_intervention()
            if iv.new_action is None:
                continue
            key = (unit.task_id, iv.effect_signature())
            if key in seen:
                continue
            seen.add(key)
            try:
                action = apply_intervention(ep.steps[iv.target_step].action, iv)
            except Exception:
                continue
            row = {
                "task_id": unit.task_id,
                "messages": [
                    {"role": "user", "content": render_context(ep, iv.target_step)},
                    {"role": "assistant", "content": json.dumps(
                        {"tool": action.tool, "args": action.args}, ensure_ascii=False)},
                ],
                "evidence_tier": unit.tier.name,
            }
            if unit.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED:
                validated.append(row)
            else:
                suggested.append(row)
    return validated, suggested


def tokens(rows):  # cheap estimate, consistent across arms
    return sum(len(m["content"]) for r in rows for m in r["messages"]) // 4


def main():
    random.seed(0)
    validated, suggested = rows_from_runs()
    random.shuffle(suggested)
    budget = tokens(validated)
    matched, total = [], 0
    for row in suggested:
        cost = tokens([row])
        if total + cost > budget * 1.05:
            continue
        matched.append(row)
        total += cost
        if total >= budget * 0.95:
            break

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (("validated", validated), ("suggested", matched)):
        with (OUT / f"c1_train_{name}.jsonl").open("w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    stats = {
        "validated": {"rows": len(validated), "tokens_est": tokens(validated)},
        "suggested_matched": {"rows": len(matched), "tokens_est": tokens(matched)},
        "suggested_pool": len(suggested),
        "train_families": sorted(TRAIN_FAMILIES.values()),
        "holdout_families": ["sqlalchemy", "networkx"],
    }
    (OUT / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
