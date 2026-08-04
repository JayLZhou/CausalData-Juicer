"""Case study #2 (evidence chain B): counterfactual step-credit
(CCPO-style ATE / rollout-tree credit assignment), expressed on
CausalData-Juicer's stored artifacts in ~50 lines — fully offline, zero replay.

For every causal unit, the paired outcomes ARE the two arms of a
per-step effect estimate: the control branch reproduces the original
outcome, the intervened branch measures the alternative, so

    ATE(step k) = P(success | do(a')) - P(success | recorded a)

with P(success | do(a')) estimated from the unit's repro runs.  Steps
without an intervention inherit credit 0 (no counterfactual evidence —
and the tier system says exactly that instead of pretending).

Run:  .venv/bin/python examples/case_credit_ate.py [--base runs/depmig-7b --pool ...]
"""

import argparse
import json
from pathlib import Path

from causal_data_juicer.compiler.common import render_action, write_jsonl
from causal_data_juicer.maintenance.revalidate import load_pooled_units

parser = argparse.ArgumentParser()
parser.add_argument("--base", default="runs/depmig-7b")
parser.add_argument("--pool", nargs="*", default=["runs/depmig-7b-fixer14b"])
parser.add_argument("--out", default="runs/case_credit_ate")
args = parser.parse_args()

_, episodes, _, units = load_pooled_units(Path(args.base), [Path(p) for p in args.pool])
eps = {ep.id: ep for ep in episodes}

rows = []
for unit in units:
    ep = eps[unit.episode_id]
    k = unit.effective_intervention().target_step
    p_do = unit.repro_flips / unit.repro_runs if unit.repro_runs else float(unit.flipped)
    p_base = 1.0 if unit.original_outcome.success else 0.0
    trajectory = [
        {
            "step": st.index,
            "action": render_action(st.action),
            "credit": round(p_do - p_base, 3) if st.index == k else 0.0,
            "counterfactual_action": render_action(unit.effective_intervention().new_action)
            if st.index == k and unit.effective_intervention().new_action
            else None,
            "has_counterfactual_evidence": st.index == k,
        }
        for st in ep.steps
    ]
    rows.append(
        {
            "task_id": unit.task_id,
            "unit_id": unit.id,
            "ate_at_target_step": round(p_do - p_base, 3),
            "trajectory": trajectory,
            "evidence_tier": unit.tier.name,
        }
    )

write_jsonl(Path(args.out) / "credit.jsonl", rows)
ates = [r["ate_at_target_step"] for r in rows]
print(
    json.dumps(
        {
            "units": len(rows),
            "mean_ate": round(sum(ates) / max(1, len(ates)), 3),
            "credited_steps": sum(1 for r in rows for s in r["trajectory"] if s["credit"] != 0),
            "out": str(Path(args.out) / "credit.jsonl"),
        },
        indent=2,
    )
)
