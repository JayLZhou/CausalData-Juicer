"""Case study #3 (evidence chain B): HER-style relabeling as an
observational operator — zero replay, zero LLM calls, ~45 lines.

Hindsight Experience Replay's trick, mapped to code agents: a failed
episode did not reach the *intended* goal, but it perfectly reached the
behavior it actually produced.  Relabel the goal to the achieved
verifier outcome and the failure becomes valid supervision for THAT
goal.  Purely observational — every row carries the OBSERVED floor,
exactly as the tier system demands.

Run:  .venv/bin/python examples/case_her_relabel.py
"""
import json
from pathlib import Path

from causal_data_juicer.acquisition.fixer import last_write_step
from causal_data_juicer.compiler.common import render_context, write_jsonl
from causal_data_juicer.run_store import RunStore
from causal_data_juicer.sdk.schemas import EvidenceTier

RUNS = ["depmig-7b", "depmig-7b-pandas", "depmig-7b-ext"]
OUT = Path("runs/case_her/her_sft.jsonl")

rows, seen = [], set()
for run in RUNS:
    store = RunStore(Path("runs") / run)
    for ep in store.load_episodes():
        if ep.outcome is None or ep.outcome.success or ep.task_id in seen:
            continue
        k = last_write_step(ep)
        if k is None:
            continue
        seen.add(ep.task_id)
        step = ep.steps[k]
        achieved = (f"running the test suite yields: {ep.outcome.passed} passed, "
                    f"{ep.outcome.failed} failed, ending with\n"
                    + "\n".join(ep.outcome.detail.splitlines()[-3:]))
        relabeled_goal = (f"Write {step.action.args.get('path')} so that {achieved}\n"
                          f"(Original context follows.)\n{render_context(ep, k)}")
        rows.append({
            "task_id": ep.task_id,
            "prompt": relabeled_goal,
            "completion": json.dumps(step.action.model_dump(), ensure_ascii=False),
            "evidence_tier": EvidenceTier.OBSERVED.name,
            "source": "her-relabel",
        })

write_jsonl(OUT, rows)
print(json.dumps({"relabeled_rows": len(rows), "out": str(OUT)}, indent=2))
