"""Training-stack export adapters (evidence chain D: adoption).

Compile validated causal units into formats mainstream trainers ingest
directly:

  trl-sft   TRL SFTTrainer chat format: {"messages": [...]}
  trl-dpo   TRL DPOTrainer format: {"prompt", "chosen", "rejected"}
  verl      verl RLHFDataset rows: {"prompt": [chat...], "data_source",
            "reward_model", "extra_info"}; written as parquet when
            pyarrow is available, JSONL otherwise.

Evidence tiers ride along in metadata fields — trainers ignore extra
columns, downstream audits don't.
"""
from __future__ import annotations

from pathlib import Path

from causal_data_juicer.compiler.common import (
    corrected_action,
    original_action,
    render_action,
    render_context,
    write_jsonl,
)
from causal_data_juicer.sdk.schemas import CausalUnit, Episode, EvidenceTier


def _rows(units: list[CausalUnit], episodes: list[Episode]):
    eps = {ep.id: ep for ep in episodes}
    for u in units:
        if u.tier < EvidenceTier.COUNTERFACTUAL_VALIDATED:
            continue
        ep = eps[u.episode_id]
        prompt = render_context(ep, u.effective_intervention().target_step)
        yield u, ep, prompt


def export_trl_sft(units, episodes, out: Path) -> Path:
    rows = [{
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": render_action(corrected_action(ep, u))},
        ],
        "evidence_tier": u.tier.name,
        "unit_id": u.id,
    } for u, ep, prompt in _rows(units, episodes)]
    return write_jsonl(out, rows)


def export_trl_dpo(units, episodes, out: Path) -> Path:
    rows = [{
        "prompt": prompt,
        "chosen": render_action(corrected_action(ep, u)),
        "rejected": render_action(original_action(ep, u)),
        "evidence_tier": u.tier.name,
        "unit_id": u.id,
    } for u, ep, prompt in _rows(units, episodes)]
    return write_jsonl(out, rows)


def export_verl(units, episodes, out: Path) -> Path:
    rows = [{
        "prompt": [{"role": "user", "content": prompt}],
        "data_source": "causal_data_juicer/" + (ep.workload_id or "unknown"),
        "reward_model": {"style": "rule", "ground_truth": render_action(corrected_action(ep, u))},
        "extra_info": {"unit_id": u.id, "task_id": u.task_id,
                       "evidence_tier": u.tier.name},
    } for u, ep, prompt in _rows(units, episodes)]
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        out = out.with_suffix(".parquet")
        out.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows), out)  # nested structs kept native
        return out
    except ImportError:
        return write_jsonl(out.with_suffix(".jsonl"), rows)


ADAPTERS = {"trl-sft": export_trl_sft, "trl-dpo": export_trl_dpo, "verl": export_verl}
