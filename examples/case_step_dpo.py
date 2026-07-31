"""Case study (evidence chain B): the tree-sampling -> step-level DPO
pipeline family (MCTS-DPO / TreeRL-style data construction), expressed
on CausalData-Juicer's public API in under 100 lines.

For each failed episode: fork the pre-step snapshot, sample K alternative
actions from the live policy at temperature>0, replay every branch, and
compile (same-state, success-vs-failure) step-level DPO pairs plus
process-reward labels — every row carrying its evidence tier.

Run:  .venv/bin/python examples/case_step_dpo.py [--tasks p01_settings ...]
"""
import argparse
import json
from pathlib import Path

from causal_data_juicer.acquisition.fixer import last_write_step
from causal_data_juicer.compiler.common import render_action, render_context, write_jsonl
from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.replay.sandbox import LocalSandbox
from causal_data_juicer.runtime.llm import DiskCachedLLM, OpenAICompatClient
from causal_data_juicer.runtime.llm_policy import extract_action
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import PytestVerifier
from causal_data_juicer.run_store import RunStore
from causal_data_juicer.sdk.schemas import Intervention, InterventionType, ToolCall

parser = argparse.ArgumentParser()
parser.add_argument("--base", default="runs/depmig-7b")
parser.add_argument("--out", default="runs/case_step_dpo")
parser.add_argument("--k", type=int, default=3)
parser.add_argument("--tasks", nargs="*", default=None)
args = parser.parse_args()

store = RunStore(Path(args.base))
episodes = [ep for ep in store.load_episodes() if not ep.outcome.success
            and (not args.tasks or ep.task_id in args.tasks)]
snapshots = store.load_snapshots()
replayer = Replayer(default_registry(), LocalSandbox(store.blobs, Path(args.out) / "scratch"),
                    PytestVerifier(timeout=120))
llm = DiskCachedLLM(OpenAICompatClient("http://127.0.0.1:8010/v1",
                                       "Qwen/Qwen2.5-7B-Instruct", temperature=0.8),
                    Path(args.out) / "llm_cache")

dpo_pairs, prm_rows, control_cache = [], [], {}
for ep in episodes:
    k_step = last_write_step(ep)
    if k_step is None:
        continue
    state = render_context(ep, k_step)
    original = ep.steps[k_step].action
    branches = [(original, False)]  # the recorded action is a known-failing branch
    for i in range(args.k):
        resp = llm.complete([
            {"role": "system", "content": "Propose the complete next write_file action as one "
             'JSON object {"tool": "write_file", "args": {"path": ..., "content": ...}}. '
             "Only installed packages are available."},
            {"role": "user", "content": f"{state}\n(variant {i}) The recorded attempt failed:\n"
             f"{render_action(original)}\nVerifier said:\n{ep.outcome.detail[-800:]}"},
        ])
        action = extract_action(resp.text)
        if not action or action.get("tool") != "write_file":
            continue
        iv = Intervention(type=InterventionType.ACTION_REPLACE, target_step=k_step,
                          new_action=ToolCall(tool="write_file", args=action["args"]),
                          source=f"resample-t0.8-v{i}")
        unit = replayer.paired_replay(ep, snapshots, iv, n_repro=2,
                                      control_cache=control_cache, early_stop_repro=True)
        branches.append((iv.new_action, unit.flipped))
        prm_rows.append({"state": state, "action": render_action(iv.new_action),
                         "label": int(unit.flipped), "task_id": ep.task_id,
                         "evidence_tier": unit.tier.name})
    for good, ok_g in branches:
        for bad, ok_b in branches:
            if ok_g and not ok_b:
                dpo_pairs.append({"prompt": state, "chosen": render_action(good),
                                  "rejected": render_action(bad), "task_id": ep.task_id,
                                  "evidence_tier": "REPRODUCIBLE"})

write_jsonl(Path(args.out) / "step_dpo.jsonl", dpo_pairs)
write_jsonl(Path(args.out) / "prm.jsonl", prm_rows)
print(json.dumps({"episodes": len(episodes), "sampled_branches": len(prm_rows),
                  "flipping_branches": sum(r["label"] for r in prm_rows),
                  "step_dpo_pairs": len(dpo_pairs)}, indent=2))
