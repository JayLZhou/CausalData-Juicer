"""Case study #5 (evidence chain B): CAPER's clause-aligned process
supervision (arXiv:2606.03327) on CausalData-Juicer's public API.

CAPER builds Text-to-SQL clause-level PRM labels by counterfactually
perturbing SQL clauses and executing the result.  Expressed here:
clause == LinePatch atom, perturbation == ToolArgumentEdit, execution ==
pytest verifier over sqlite, attribution == paired replay + ddmin
minimal slice, labels == compiled clause-PRM rows.  Both directions run:
repair (fail->pass, evidence-tiered units) and stress (pass->fail
criticality — the v2 direction, same machinery, opposite sign).

Run:  .venv/bin/python examples/case_caper_clause_prm.py
"""
import json
from pathlib import Path

from caper_workload import REPAIR, STRESS

from causal_data_juicer.compiler.common import write_jsonl
from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.replay.sandbox import LocalSandbox
from causal_data_juicer.runtime.agent import ScriptedPolicy, ScriptedStep
from causal_data_juicer.runtime.collector import Collector
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import PytestVerifier
from causal_data_juicer.sdk.schemas import ArgEdit, CostLedger, Intervention, InterventionType, LinePatch, ToolCall
from causal_data_juicer.slicing.ddmin import minimize_unit
from causal_data_juicer.store.blob import BlobStore

OUT = Path("runs/case_caper")
blobs = BlobStore(OUT / "blobs")
verifier = PytestVerifier(timeout=60)
collector = Collector(default_registry(), blobs, verifier)
replayer = Replayer(default_registry(), LocalSandbox(blobs, OUT / "scratch"), verifier)
ledger, rows = CostLedger(), []


def collect(task, sql_lines):
    ws = OUT / "workspaces" / task["id"]
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "test_solution.py").write_text(task["test"])
    policy = ScriptedPolicy([
        ScriptedStep(action=ToolCall(tool="write_file",
                                     args={"path": "solution.sql",
                                           "content": "\n".join(sql_lines) + "\n"})),
        ScriptedStep(action=ToolCall(tool="run_pytest", args={})),
    ])
    return collector.run_episode(task["id"], task["question"], ws, policy)


def clause_edit(patches):
    return Intervention(type=InterventionType.TOOL_ARGUMENT_EDIT, target_step=0,
                        edits=[ArgEdit(arg="content", op="patch_lines",
                                       patches=[LinePatch(line=l, text=t) for l, t in patches])])


# -- repair direction: which clauses causally fix the failure? --------------
episode, snapshots = collect(REPAIR, REPAIR["wrong_sql"])
assert not episode.outcome.success
unit = replayer.paired_replay(episode, snapshots,
                              clause_edit(list(REPAIR["clause_fixes"].items())), n_repro=3)
unit = minimize_unit(replayer, episode, snapshots, unit)
minimal_lines = sorted(p.line for e in unit.effective_intervention().edits for p in e.patches)
for line, text in REPAIR["clause_fixes"].items():
    rows.append({"task_id": REPAIR["id"], "direction": "repair", "clause_line": line,
                 "clause": text, "in_minimal_causal_set": line in minimal_lines,
                 "evidence_tier": unit.tier.name})

# -- stress direction: which clauses are critical in a CORRECT query? -------
episode_s, snapshots_s = collect(STRESS, STRESS["correct_sql"])
assert episode_s.outcome.success
for line, alternatives in STRESS["perturbations"].items():
    for alt in alternatives:
        outcome = replayer.intervened_flip(episode_s, snapshots_s,
                                           clause_edit([(line, alt)]), ledger)
        rows.append({"task_id": STRESS["id"], "direction": "stress", "clause_line": line,
                     "clause": alt, "critical": not outcome.success,
                     "evidence": "executed-counterfactual"})

write_jsonl(OUT / "clause_prm.jsonl", rows)
summary = {
    "repair": {"flipped": unit.flipped, "tier": unit.tier.name,
               "minimal_clause_lines": minimal_lines,
               "atoms": f"{unit.atoms_before_slicing}->{unit.atoms_after_slicing}"},
    "stress": {"perturbations": sum(len(v) for v in STRESS["perturbations"].values()),
               "critical": sum(1 for r in rows if r["direction"] == "stress" and r["critical"]),
               "harmless": sum(1 for r in rows if r["direction"] == "stress" and not r["critical"])},
    "clause_prm_rows": len(rows),
}
print(json.dumps(summary, indent=2))
