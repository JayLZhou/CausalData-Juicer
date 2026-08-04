import json
from pathlib import Path

import pytest

from causal_data_juicer.compiler.adapters import export_trl_dpo, export_trl_sft, export_verl
from causal_data_juicer.sdk.schemas import (
    CausalUnit,
    Episode,
    EvidenceTier,
    Intervention,
    InterventionType,
    Outcome,
    Step,
    ToolCall,
)


@pytest.fixture
def unit_and_episode():
    bad = ToolCall(tool="write_file", args={"path": "solution.py", "content": "bad\n"})
    good = ToolCall(tool="write_file", args={"path": "solution.py", "content": "good\n"})
    ep = Episode(
        task_id="t1",
        workload_id="wl",
        task_description="fix it",
        steps=[Step(index=0, action=bad, observation="wrote")],
        outcome=Outcome(success=False),
    )
    unit = CausalUnit(
        episode_id=ep.id,
        task_id="t1",
        intervention=Intervention(
            type=InterventionType.ACTION_REPLACE, target_step=0, new_action=good
        ),
        original_outcome=ep.outcome,
        flipped=True,
        tier=EvidenceTier.REPRODUCIBLE,
    )
    low = unit.model_copy(deep=True)
    low.tier = EvidenceTier.SUGGESTED  # must be excluded everywhere
    return [unit, low], [ep]


def test_trl_dpo_format(unit_and_episode, tmp_path):
    units, eps = unit_and_episode
    path = export_trl_dpo(units, eps, tmp_path / "dpo.jsonl")
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    assert len(rows) == 1  # SUGGESTED row excluded
    row = rows[0]
    assert set(row) >= {"prompt", "chosen", "rejected", "evidence_tier"}
    assert "good" in row["chosen"] and "bad" in row["rejected"]
    assert row["evidence_tier"] == "REPRODUCIBLE"


def test_trl_sft_messages_format(unit_and_episode, tmp_path):
    units, eps = unit_and_episode
    path = export_trl_sft(units, eps, tmp_path / "sft.jsonl")
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    assert len(rows) == 1
    roles = [m["role"] for m in rows[0]["messages"]]
    assert roles == ["user", "assistant"]
    assert "good" in rows[0]["messages"][1]["content"]


def test_verl_parquet_roundtrip(unit_and_episode, tmp_path):
    pq = pytest.importorskip("pyarrow.parquet")
    units, eps = unit_and_episode
    path = export_verl(units, eps, tmp_path / "verl")
    assert path.suffix == ".parquet"
    table = pq.read_table(path)
    assert table.num_rows == 1
    row = table.to_pylist()[0]
    assert row["prompt"][0]["role"] == "user"
    assert row["reward_model"]["style"] == "rule"
    assert row["extra_info"]["evidence_tier"] == "REPRODUCIBLE"
