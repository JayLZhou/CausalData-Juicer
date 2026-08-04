"""Shared rendering helpers for exported views.

Hard rule: every exported row carries ``evidence_tier`` — weak evidence
never masquerades as strong.
"""

from __future__ import annotations

import json
from pathlib import Path

from causal_data_juicer.interventions.apply import apply_intervention
from causal_data_juicer.sdk.schemas import CausalUnit, Episode, ToolCall


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def render_context(episode: Episode, target_step: int) -> str:
    """The prompt context an agent saw just before the target step."""
    lines = [f"Task: {episode.task_description}".strip()]
    for step in episode.steps[:target_step]:
        lines.append(f"[step {step.index}] {render_action(step.action)}")
        lines.append(f"[obs {step.index}] {step.observation}")
    lines.append(f"[step {target_step}] your next action:")
    return "\n".join(lines)


def render_action(action: ToolCall) -> str:
    return json.dumps({"tool": action.tool, "args": action.args}, ensure_ascii=False)


def corrected_action(episode: Episode, unit: CausalUnit) -> ToolCall:
    iv = unit.effective_intervention()
    original = episode.steps[iv.target_step].action
    return apply_intervention(original, iv)


def original_action(episode: Episode, unit: CausalUnit) -> ToolCall:
    return episode.steps[unit.effective_intervention().target_step].action
