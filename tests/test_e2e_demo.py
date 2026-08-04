"""End-to-end demo pipeline test: the M1 kill-line check in CI form."""

import json
from pathlib import Path

from causal_data_juicer.pipeline import run_demo
from causal_data_juicer.run_store import RunStore
from causal_data_juicer.sdk.schemas import EvidenceTier


def test_demo_end_to_end(tmp_path):
    run_dir = tmp_path / "run"
    report = run_demo(run_dir, n_repro=2)

    assert report["episodes"] == 9
    assert report["failed_episodes"] == 6
    assert report["candidates_screened"] == 7
    assert report["determinism_control_ok"] is True
    assert report["control_digest_match_rate"] == 1.0  # instrument upper bound on toy

    # Kill line #1: flip reproducibility on the deterministic subset >= 90%.
    assert report["flip_repro_rate"] >= 0.9

    store = RunStore(run_dir)
    units = store.load_units()
    minimal = [u for u in units if u.tier == EvidenceTier.MINIMAL]
    rejected = [u for u in units if not u.flipped]
    assert len(minimal) == 6
    assert len(rejected) == 1  # t09's cosmetic non-fix must not validate

    # Causal slicing dropped t06's cosmetic atom.
    t06 = next(u for u in units if u.task_id == "t06_prime")
    assert t06.atoms_before_slicing == 2 and t06.atoms_after_slicing == 1

    # Every unit is provenance-stamped; every export row carries its tier.
    assert all(u.provenance.get("workload_digest") for u in units)
    for name in ("sft", "dpo", "memory", "regression"):
        rows = [json.loads(line) for line in Path(report["exports"][name]).read_text().splitlines()]
        assert len(rows) == 6
        assert all(row["evidence_tier"] == "MINIMAL" for row in rows)

    # Exported counterfactual cases replay: spot-check one.
    case = json.loads(Path(report["exports"]["regression"]).read_text().splitlines()[0])
    ok, detail = store.replay_regression_case(case, scratch=tmp_path / "regress")
    assert ok, detail
