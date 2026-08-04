"""Case study #8 (wishlist rank 1): RAG context attribution by ablation
— ContextCite's leave-out semantics, executed on recorded trajectories.

Context assembly is a trajectory step (write context.md); ablating a
document is an intervention on that step; the reader agent *re-reacts*
to the reduced context (reactive continuation); the verifier decides if
the answer survives. Documents whose removal breaks the answer are its
causal supports — pass→fail attribution, the stress direction at work.

Run:  .venv/bin/python examples/case_context_ablate.py
"""

import json
from pathlib import Path

from causal_data_juicer.compiler.common import write_jsonl
from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.replay.sandbox import UnsafeLocalWorkspace
from causal_data_juicer.runtime.collector import Collector
from causal_data_juicer.runtime.llm import DiskCachedLLM, OpenAICompatClient
from causal_data_juicer.runtime.llm_policy import LLMPolicy
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import CommandVerifier
from causal_data_juicer.sdk.schemas import Intervention, InterventionType, ToolCall
from causal_data_juicer.store.blob import BlobStore

OUT = Path("runs/case_context_ablate")
READER_SYS = """\
You are a QA agent. context.md (already written; its full content is in the
history) contains retrieved documents. Answer ONLY from that context.
You have NOT finished until answer.txt exists: your FIRST reply must be
{"tool": "write_file", "args": {"path": "answer.txt", "content": "<one-line answer>"}}
and only AFTER that observation may you reply {"tool": "done", "args": {}}."""

TASK = {
    "question": "In which year did the fictional Meridian Accord enter into force?",
    "gold": "1987",
    "docs": {
        "doc1_treaty": "The Meridian Accord, signed in Geneva, entered into force in 1987 after ratification by nine states.",
        "doc2_context": "Ratification required nine of twelve signatories; the ninth instrument was deposited by Portugal.",
        "doc3_distractor": "The Meridian Hotel in Lisbon opened its rooftop restaurant in 2003.",
        "doc4_distractor": "Accord is also the name of a sedan produced continuously since 1976.",
    },
    "essential": ["doc1_treaty"],
}


def context_md(docs: dict) -> str:
    return "\n".join(f"## {name}\n{text}\n" for name, text in docs.items())


class RagPolicy:
    """Step 0: assemble retrieved context (recorded); then a live reader."""

    def __init__(self, reader: LLMPolicy, docs: dict):
        self.reader, self.docs = reader, docs

    def next_action(self, task_id, idx, history):
        if idx == 0:
            return ToolCall(
                tool="write_file", args={"path": "context.md", "content": context_md(self.docs)}
            ), None
        return self.reader.next_action(task_id, idx, history)


verifier = CommandVerifier(
    [
        "{python}",
        "-c",
        (
            f"import pathlib,sys; sys.exit(0 if '{TASK['gold']}' in "
            f"pathlib.Path('answer.txt').read_text() else 1)"
        ),
    ]
)
blobs = BlobStore(OUT / "blobs")
collector = Collector(default_registry(), blobs, verifier)
replayer = Replayer(default_registry(), UnsafeLocalWorkspace(blobs, OUT / "scratch"), verifier)
llm = DiskCachedLLM(
    OpenAICompatClient("http://127.0.0.1:8021/v1", "Qwen/Qwen2.5-7B-Instruct"), OUT / "llm_cache"
)

ws = OUT / "workspaces" / "rag"
ws.mkdir(parents=True, exist_ok=True)
reader = LLMPolicy(llm, max_steps=4, system_prompt=READER_SYS)
reader.bind_task(TASK["question"])
episode, snapshots = collector.run_episode(
    "rag", TASK["question"], ws, RagPolicy(reader, TASK["docs"])
)
assert episode.outcome.success, "reader must answer correctly with full context"

rows = []
for name in TASK["docs"]:
    reduced = {k: v for k, v in TASK["docs"].items() if k != name}
    drop = Intervention(
        type=InterventionType.ACTION_REPLACE,
        target_step=0,
        new_action=ToolCall(
            tool="write_file", args={"path": "context.md", "content": context_md(reduced)}
        ),
        source=f"ablate:{name}",
    )
    unit = replayer.paired_replay(episode, snapshots, drop, n_repro=1, continuation_policy=reader)
    survived = bool(unit.intervened_outcome and unit.intervened_outcome.success)
    rows.append(
        {
            "doc": name,
            "answer_survived_without_it": survived,
            "causal_support": not survived,
            "control_matched": unit.original_replay_match,
            "expected_essential": name in TASK["essential"],
        }
    )

write_jsonl(OUT / "context_credit.jsonl", rows)
correct = sum(r["causal_support"] == r["expected_essential"] for r in rows)
print(
    json.dumps(
        {
            "docs": len(rows),
            "supports_found": [r["doc"] for r in rows if r["causal_support"]],
            "attribution_accuracy": f"{correct}/{len(rows)}",
        },
        indent=2,
    )
)
