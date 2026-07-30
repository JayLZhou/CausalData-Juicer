"""LLM fixer candidate source for the depmig bench.

For a failed episode, ask the (cached) model for a corrected version of
the file the agent last wrote, and propose it as an ACTION_REPLACE at
that step.  The fixer sees exactly what an engineer would: the task
brief, the agent's final file, and the failing verifier output — never
the bench's answer key (migration_points stay hidden).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from causeforge.runtime.llm import LLMClient
from causeforge.runtime.llm_policy import extract_action
from causeforge.sdk.schemas import (
    Episode,
    Intervention,
    InterventionType,
    ToolCall,
)

FIXER_SYSTEM = """\
You are a senior engineer reviewing a failed coding-agent run.
You will get the task brief, the last file the agent wrote, and the failing
test output. Reply with EXACTLY one JSON object containing the corrected,
complete file: {"tool": "write_file", "args": {"path": "<same path>", "content": "<full corrected content>"}}
Do not change the path unless the path itself is the bug. No other text."""


def last_write_step(episode: Episode) -> int | None:
    for step in reversed(episode.steps):
        if step.action.tool == "write_file":
            return step.index
    return None


@dataclass
class FixerLLMSource:
    llm: LLMClient
    candidates_per_failure: int = 1
    name: str = "fixer-llm"

    def propose(self, episode: Episode) -> list[Intervention]:
        k = last_write_step(episode)
        if k is None or episode.outcome is None:
            return []
        step = episode.steps[k]
        messages = [
            {"role": "system", "content": FIXER_SYSTEM},
            {"role": "user", "content": (
                f"Task brief:\n{episode.task_description}\n\n"
                f"Agent's last written file ({step.action.args.get('path')}):\n"
                f"```python\n{step.action.args.get('content', '')}\n```\n\n"
                f"Failing verifier output:\n{episode.outcome.detail}"
            )},
        ]
        out: list[Intervention] = []
        for i in range(self.candidates_per_failure):
            msgs = messages if i == 0 else messages + [
                {"role": "user", "content": f"Give an alternative fix (variant {i})."}
            ]
            resp = self.llm.complete(msgs)
            action = extract_action(resp.text)
            if not action or action.get("tool") != "write_file":
                continue
            args = action.get("args") or {}
            if not args.get("path") or not isinstance(args.get("content"), str):
                continue
            out.append(Intervention(
                type=InterventionType.ACTION_REPLACE,
                target_step=k,
                new_action=ToolCall(tool="write_file", args={
                    "path": args["path"], "content": args["content"]}),
                rationale=f"fixer-llm candidate {i} (cached={resp.cached})",
                source=self.name,
            ))
        return out
