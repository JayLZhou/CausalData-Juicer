"""Case study #9 (wishlist rank 2): Thought-Anchors-style step credit —
resample one reasoning sentence, let the rest of the chain re-roll, and
measure how often the final answer survives.

Each thought is a trajectory step (thoughts.md grows one numbered line
per step; the final step writes answer.txt). The intervention swaps
thought *i* for a temperature-resampled alternative; reactive
continuation regenerates thoughts i+1… and the answer; the verifier
diffs outcomes. Low survival under resampling = a critical anchor.

Run:  .venv/bin/python examples/case_thought_anchors.py
"""
import json
from pathlib import Path

from causal_data_juicer.compiler.common import write_jsonl
from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.replay.sandbox import LocalSandbox
from causal_data_juicer.runtime.collector import Collector
from causal_data_juicer.runtime.llm import DiskCachedLLM, OpenAICompatClient
from causal_data_juicer.runtime.llm_policy import LLMPolicy, extract_action
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import CommandVerifier
from causal_data_juicer.sdk.schemas import Intervention, InterventionType, ToolCall
from causal_data_juicer.store.blob import BlobStore

OUT = Path("runs/case_thought_anchors")
PROBLEM = ("A workshop has 3 machines. Each machine produces 14 parts per hour. "
           "The workshop runs 6 hours a day but one machine is down for the "
           "first 2 hours. How many parts are produced in one day?")
GOLD = "224"   # 2h * 2 * 14 + 4h * 3 * 14 = 56 + 168

THINKER_SYS = """\
You are a careful solver working in numbered thoughts, one per turn.
EVERY reply must be exactly ONE JSON tool call, no other text.
Turn format, in order:
1..4: {"tool": "write_file", "args": {"path": "thoughts.md", "content": "<ALL previous thought lines plus exactly one new line: N. <thought>>"}}
then: {"tool": "write_file", "args": {"path": "answer.txt", "content": "<numeric answer>"}}
then: {"tool": "done", "args": {}}"""

K_RESAMPLES = 2

verifier = CommandVerifier(
    ["{python}", "-c",
     f"import pathlib,sys; sys.exit(0 if '{GOLD}' in "
     f"pathlib.Path('answer.txt').read_text() else 1)"])
blobs = BlobStore(OUT / "blobs")
collector = Collector(default_registry(), blobs, verifier)
replayer = Replayer(default_registry(), LocalSandbox(blobs, OUT / "scratch"), verifier)
llm0 = DiskCachedLLM(OpenAICompatClient("http://127.0.0.1:8021/v1",
                                        "Qwen/Qwen2.5-7B-Instruct"), OUT / "llm_cache")
llm_hot = DiskCachedLLM(OpenAICompatClient("http://127.0.0.1:8021/v1",
                                           "Qwen/Qwen2.5-7B-Instruct",
                                           temperature=0.9), OUT / "llm_cache")

class Stepify:
    """Mechanically decompose a dumped multi-thought write into one step
    per thought (cumulative prefixes) — model-agnostic incrementality."""

    def __init__(self, inner):
        self.inner, self.queue = inner, []

    def next_action(self, task_id, idx, history):
        if self.queue:
            return self.queue.pop(0)
        nxt = self.inner.next_action(task_id, idx, history)
        if nxt is None:
            return None
        action, llm = nxt
        if (action.tool == "write_file"
                and action.args.get("path") == "thoughts.md"):
            lines = action.args["content"].splitlines()
            if len(lines) > 1:
                for i in range(1, len(lines) + 1):
                    self.queue.append((ToolCall(tool="write_file",
                                                args={"path": "thoughts.md",
                                                      "content": "\n".join(lines[:i])}),
                                       llm if i == 1 else None))
                return self.queue.pop(0)
        return nxt


ws = OUT / "workspaces" / "solve"
ws.mkdir(parents=True, exist_ok=True)
thinker = LLMPolicy(llm0, max_steps=6, system_prompt=THINKER_SYS)
thinker.bind_task(PROBLEM)
episode, snapshots = collector.run_episode("anchors", PROBLEM, ws, Stepify(thinker))
baseline_ok = episode.outcome.success
direction = "stress (which thought, changed, breaks it)" if baseline_ok \
    else "repair (which thought, changed, fixes it)"
thought_steps = [s for s in episode.steps
                 if s.action.args.get("path") == "thoughts.md"]

rows = []
for step in thought_steps:
    survived = 0
    for v in range(K_RESAMPLES):
        prefix = "\n".join(step.action.args["content"].splitlines()[:-1])
        resp = llm_hot.complete([
            {"role": "system", "content": THINKER_SYS + f" /variant {v}"},
            {"role": "user", "content": f"Task: {PROBLEM}\nThoughts so far:\n{prefix}\n"
             "Give your next reply (the write_file for thoughts.md with one new thought)."}])
        action = extract_action(resp.text)
        if not action or action.get("tool") != "write_file":
            continue
        swap = Intervention(type=InterventionType.ACTION_REPLACE,
                            target_step=step.index,
                            new_action=ToolCall(tool="write_file", args=action["args"]),
                            source=f"resample-thought-{step.index}-v{v}")
        unit = replayer.paired_replay(episode, snapshots, swap, n_repro=1,
                                      continuation_policy=thinker)
        new_ok = bool(unit.intervened_outcome and unit.intervened_outcome.success)
        survived += (new_ok != baseline_ok)   # outcome flipped vs baseline
    original_thought = step.action.args["content"].splitlines()[-1]
    rows.append({"step": step.index, "thought": original_thought[:90],
                 "resamples": K_RESAMPLES, "flips": survived,
                 "anchor_score": round(survived / K_RESAMPLES, 2)})

write_jsonl(OUT / "thought_anchors.jsonl", rows)
print(json.dumps({"baseline_correct": baseline_ok, "direction": direction,
                  "thoughts": len(rows),
                  "anchors": [r["thought"] for r in rows if r["anchor_score"] >= 0.5]},
                 indent=2))
