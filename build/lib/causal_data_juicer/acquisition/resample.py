"""Policy-resampling candidate source (promoted from case study #1).

Third candidate source class alongside fix tables and fixer-LLMs:
re-sample the *policy itself* at temperature > 0 for alternative actions
at the failure's last write step.  The B1 case study showed this flips
tasks the entire fixer pool misses; A10's layered result says pooling
heterogeneous sources is the coverage strategy — so here it becomes a
first-class source the screener can mix in.
"""
from __future__ import annotations

from dataclasses import dataclass

from causal_data_juicer.acquisition.fixer import last_write_step
from causal_data_juicer.runtime.llm import LLMClient
from causal_data_juicer.runtime.llm_policy import extract_action
from causal_data_juicer.sdk.schemas import (
    CostLedger,
    Episode,
    Intervention,
    InterventionType,
    ToolCall,
)

RESAMPLE_SYSTEM = """\
You are retrying a failed coding step. Propose a complete alternative
write_file action as EXACTLY one JSON object:
{"tool": "write_file", "args": {"path": "<path>", "content": "<full file content>"}}
Only the packages named in the task brief plus the standard library are
installed. Do not repeat the failed attempt verbatim. No other text."""


@dataclass
class ResampleSource:
    llm: LLMClient  # temperature > 0 client (disk-cached like everything else)
    k: int = 3
    name: str = "resample"
    ledger: CostLedger | None = None

    def propose(self, episode: Episode) -> list[Intervention]:
        step_index = last_write_step(episode)
        if step_index is None or episode.outcome is None:
            return []
        step = episode.steps[step_index]
        out: list[Intervention] = []
        for i in range(self.k):
            messages = [
                {"role": "system", "content": RESAMPLE_SYSTEM},
                {"role": "user", "content": (
                    f"Task brief:\n{episode.task_description}\n\n"
                    f"(variant {i}) The recorded attempt failed:\n"
                    f"path: {step.action.args.get('path')}\n"
                    f"```python\n{step.action.args.get('content', '')}\n```\n\n"
                    f"Verifier output:\n{episode.outcome.detail[-800:]}"
                )},
            ]
            resp = self.llm.complete(messages)
            if self.ledger is not None and not resp.cached:
                self.ledger.charge_llm(resp.tokens_in, resp.tokens_out, dollars=resp.dollars)
            action = extract_action(resp.text)
            if not action or action.get("tool") != "write_file":
                continue
            args = action.get("args") or {}
            if not args.get("path") or not isinstance(args.get("content"), str):
                continue
            out.append(Intervention(
                type=InterventionType.ACTION_REPLACE,
                target_step=step_index,
                new_action=ToolCall(tool="write_file",
                                    args={"path": args["path"], "content": args["content"]}),
                rationale=f"policy resample variant {i}",
                source=f"{self.name}-v{i}",
            ))
        return out
