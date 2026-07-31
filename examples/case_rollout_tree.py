"""Case study #4 (evidence chain B): rollout-tree credit assignment
(Tree-GRPO / RTMC family) on the public API, under 100 lines.

Build a depth-2 counterfactual tree per failed episode: level 1 samples
K alternative actions at the fork point; each failing level-1 branch
gets a level-2 revision conditioned on ITS OWN executed failure output
(feedback only a replay engine provides).  Per-node credit is the
group-relative advantage — node subtree success minus the sibling-group
mean — i.e. exactly the data core of tree-based GRPO methods.

Run:  .venv/bin/python examples/case_rollout_tree.py [--tasks ...] [--k 3]
"""
import argparse
import json
from pathlib import Path

from causeforge.acquisition.fixer import last_write_step, propose_refinement
from causeforge.acquisition.resample import ResampleSource
from causeforge.compiler.common import render_action, write_jsonl
from causeforge.replay.replayer import Replayer
from causeforge.replay.sandbox import LocalSandbox
from causeforge.runtime.llm import DiskCachedLLM, OpenAICompatClient
from causeforge.runtime.tools import default_registry
from causeforge.runtime.verifier import PytestVerifier
from causeforge.run_store import RunStore
from causeforge.sdk.schemas import CostLedger

parser = argparse.ArgumentParser()
parser.add_argument("--base", default="runs/depmig-7b")
parser.add_argument("--base-url", default="http://127.0.0.1:8014/v1")
parser.add_argument("--tasks", nargs="*", default=["p02_str_coercion", "k01_info", "s03_engine_execute"])
parser.add_argument("--k", type=int, default=3)
parser.add_argument("--out", default="runs/case_rollout_tree")
args = parser.parse_args()

store = RunStore(Path(args.base))
episodes = [ep for ep in store.load_episodes()
            if not ep.outcome.success and ep.task_id in args.tasks]
snapshots = store.load_snapshots()
replayer = Replayer(default_registry(), LocalSandbox(store.blobs, Path(args.out) / "scratch"),
                    PytestVerifier(timeout=120))
llm = DiskCachedLLM(OpenAICompatClient(args.base_url, "Qwen/Qwen2.5-7B-Instruct",
                                       temperature=0.9), Path(args.out) / "llm_cache")
sampler = ResampleSource(llm, k=args.k)
ledger = CostLedger()

nodes = []
for ep in episodes:
    root_children = []
    for iv in sampler.propose(ep):
        outcome = replayer.intervened_flip(ep, snapshots, iv, ledger)
        child = {"task_id": ep.task_id, "depth": 1, "action": render_action(iv.new_action),
                 "success": outcome.success, "children": []}
        if not outcome.success:  # expand failing branches with executed feedback
            revised = propose_refinement(llm, ep, iv, outcome.detail, 1)
            if revised is not None:
                sub = replayer.intervened_flip(ep, snapshots, revised, ledger)
                child["children"].append({"task_id": ep.task_id, "depth": 2,
                                          "action": render_action(revised.new_action),
                                          "success": sub.success, "children": []})
        root_children.append(child)

    def subtree_value(node):  # success anywhere below counts
        return max([float(node["success"])] + [subtree_value(c) for c in node["children"]])

    def assign(siblings):
        if not siblings:
            return
        mean = sum(subtree_value(c) for c in siblings) / len(siblings)
        for c in siblings:
            c["advantage"] = round(subtree_value(c) - mean, 3)
            assign(c["children"])
    assign(root_children)
    nodes.extend(root_children)

flat = []
def flatten(n):
    flat.append({key: n[key] for key in ("task_id", "depth", "action", "success", "advantage")})
    for c in n["children"]:
        flatten(c)
for n in nodes:
    flatten(n)

write_jsonl(Path(args.out) / "tree_credit.jsonl", flat)
print(json.dumps({"episodes": len(episodes), "nodes": len(flat),
                  "successes": sum(f["success"] for f in flat),
                  "replays": ledger.replay_runs,
                  "nonzero_advantages": sum(1 for f in flat if f.get("advantage"))}, indent=2))
