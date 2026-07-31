import json

from causal_data_juicer.compiler.observational import compile_observational
from causal_data_juicer.runtime.import_trace import load_generic_traces

TRACES = [
    {"task_id": "ok1", "description": "add numbers", "success": True,
     "steps": [{"tool": "write_file", "args": {"path": "s.py", "content": "x=1\n"},
                "observation": "wrote s.py"},
               {"tool": "run_pytest", "args": {}, "observation": "exit=0 passed=1"}]},
    {"task_id": "bad1", "description": "parse dates", "success": False,
     "outcome_detail": "AssertionError: wrong month",
     "steps": [{"tool": "write_file", "args": {"path": "p.py", "content": "y=2\n"},
                "observation": "wrote p.py"}]},
]


def _trace_file(tmp_path):
    p = tmp_path / "traces.jsonl"
    p.write_text("\n".join(json.dumps(t) for t in TRACES) + "\n")
    return p


def test_import_builds_episodes(tmp_path):
    episodes = load_generic_traces(_trace_file(tmp_path))
    assert len(episodes) == 2
    ok = episodes[0]
    assert ok.outcome.success and len(ok.steps) == 2
    assert ok.steps[0].obs_digest  # digests computed even without snapshots
    assert ok.meta["import_mode"] is True


def test_observational_ceiling_is_visible_everywhere(tmp_path):
    episodes = load_generic_traces(_trace_file(tmp_path))
    exports = compile_observational(episodes, tmp_path / "exports")

    bc = [json.loads(l) for l in open(exports["bc_sft"])]
    assert len(bc) == 2  # 2 steps of the one successful episode
    assert all(r["evidence_tier"] == "OBSERVED" for r in bc)
    assert "write_file" in bc[0]["completion"]

    failures = [json.loads(l) for l in open(exports["failures"])]
    assert len(failures) == 1
    assert failures[0]["evidence_tier"] == "OBSERVED"
    assert "wrong month" in failures[0]["outcome"]
