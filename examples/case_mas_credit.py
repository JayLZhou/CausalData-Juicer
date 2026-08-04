"""Case study #7 (landscape row G): message-level credit in a two-agent
team, via reactive paired replay.

A planner posts PLAN.md (its message); a live coder implements it
faithfully; a flawed plan dooms the team. The intervention edits the
MESSAGE — and unlike recorded replay, the coder *re-reacts live* to the
new plan (Replayer's continuation_policy). Outcome flips attribute the
team failure to the message: COMA-style counterfactual credit, executed.

Run:  .venv/bin/python examples/case_mas_credit.py
"""

import json
from pathlib import Path

from causal_data_juicer.compiler.common import write_jsonl
from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.replay.sandbox import LocalSandbox
from causal_data_juicer.runtime.collector import Collector
from causal_data_juicer.runtime.llm import DiskCachedLLM, OpenAICompatClient
from causal_data_juicer.runtime.llm_policy import LLMPolicy
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import PytestVerifier
from causal_data_juicer.sdk.schemas import Intervention, InterventionType, ToolCall
from causal_data_juicer.store.blob import BlobStore

OUT = Path("runs/case_mas_credit")
CODER_SYS = """\
You are the CODER in a two-agent team. PLAN.md (already written by the
planner) is in the history. Implement it EXACTLY in solution.py, run the
tests, then reply {"tool": "done", "args": {}}. Tools: read_file /
write_file / run_pytest / done — one JSON object per reply."""

TASKS = [
    {
        "id": "mas_parity",
        "test": (
            "from solution import label\n\n"
            "def test_label():\n"
            "    assert label(2) == 'even' and label(3) == 'odd'\n"
        ),
        "bad_plan": "Implement label(n) in solution.py returning the boolean n % 2 == 0.",
        "good_plan": "Implement label(n) in solution.py returning the STRING 'even' "
        "if n is even else the STRING 'odd'.",
    },
    {
        "id": "mas_convert",
        "test": (
            "from solution import convert\n\n"
            "def test_convert():\n"
            "    assert convert(0) == 32.0 and convert(100) == 212.0\n"
        ),
        "bad_plan": "Implement convert(t) in solution.py converting Fahrenheit to "
        "Celsius: (t - 32) * 5 / 9.",
        "good_plan": "Implement convert(t) in solution.py converting CELSIUS TO "
        "FAHRENHEIT: t * 9 / 5 + 32.",
    },
]


class TeamPolicy:
    """Step 0: the planner's (recorded, flawed) message; then a live coder."""

    def __init__(self, coder: LLMPolicy, plan: str):
        self.coder, self.plan = coder, plan

    def next_action(self, task_id, idx, history):
        if idx == 0:
            return ToolCall(tool="write_file", args={"path": "PLAN.md", "content": self.plan}), None
        return self.coder.next_action(task_id, idx, history)


blobs = BlobStore(OUT / "blobs")
collector = Collector(default_registry(), blobs, PytestVerifier())
replayer = Replayer(default_registry(), LocalSandbox(blobs, OUT / "scratch"), PytestVerifier())
llm = DiskCachedLLM(
    OpenAICompatClient("http://127.0.0.1:8021/v1", "Qwen/Qwen2.5-7B-Instruct"), OUT / "llm_cache"
)

rows = []
for task in TASKS:
    ws = OUT / "workspaces" / task["id"]
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "test_solution.py").write_text(task["test"])
    coder = LLMPolicy(llm, max_steps=6, system_prompt=CODER_SYS)
    coder.bind_task(f"Team task {task['id']}: implement per PLAN.md.")
    episode, snapshots = collector.run_episode(
        task["id"], f"Team task {task['id']}", ws, TeamPolicy(coder, task["bad_plan"])
    )
    message_edit = Intervention(
        type=InterventionType.ACTION_REPLACE,
        target_step=0,
        new_action=ToolCall(
            tool="write_file", args={"path": "PLAN.md", "content": task["good_plan"]}
        ),
        source="message-edit",
        rationale="counterfactual planner message",
    )
    unit = replayer.paired_replay(
        episode, snapshots, message_edit, n_repro=2, continuation_policy=coder
    )
    rows.append(
        {
            "task_id": task["id"],
            "team_failed": not episode.outcome.success,
            "message_blamed": unit.flipped,
            "credit": (unit.repro_flips / unit.repro_runs)
            if unit.repro_runs
            else float(unit.flipped),
            "control_matched": unit.original_replay_match,
            "coder_rereacted": True,
            "evidence_tier": unit.tier.name,
        }
    )

write_jsonl(OUT / "mas_credit.jsonl", rows)
print(
    json.dumps(
        {
            "teams": len(rows),
            "failures": sum(r["team_failed"] for r in rows),
            "messages_blamed": sum(r["message_blamed"] for r in rows),
        },
        indent=2,
    )
)
