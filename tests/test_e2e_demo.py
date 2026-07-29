"""End-to-end demo pipeline test: the M1 kill-line check in CI form."""
import json

from causeforge.pipeline import run_demo
from causeforge.run_store import RunStore
from causeforge.sdk.schemas import EvidenceTier


def test_demo_end_to_end(tmp_path):
    run_dir = tmp_path / "run"
    report = run_demo(run_dir, n_repro=2)

    assert report["episodes"] == 9
    assert report["failed_episodes"] == 6
    assert report["candidates_screened"] == 7
    assert report["determinism_control_ok"] is True

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
        rows = [json.loads(l) for l in open(report["exports"][name])]
        assert len(rows) == 6
        assert all(row["evidence_tier"] == "MINIMAL" for row in rows)

    # Exported counterfactual cases replay: spot-check one.
    case = json.loads(open(report["exports"]["regression"]).readline())
    ok, detail = store.replay_regression_case(case, scratch=tmp_path / "regress")
    assert ok, detail
