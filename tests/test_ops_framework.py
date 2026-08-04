"""DJ-style ops framework: registry, categories, recipe execution."""

import pytest

from causal_data_juicer.ops import ops_zoo  # noqa: F401
from causal_data_juicer.ops.base_op import OPERATORS
from causal_data_juicer.ops.recipe import list_ops, run_recipe
from causal_data_juicer.sdk.schemas import EvidenceTier

RECIPE = """\
workdir: {workdir}
process:
  - collect_toy: {{}}
  - screen_failures: {{}}
  - paired_replay: {{n_repro: 2}}
  - minimize: {{}}
  - export_views: {{}}
  - save_run: {{}}
"""


def test_registry_has_all_categories():
    cats = {cls.category for _, cls in OPERATORS.items()}
    assert cats == {"observational", "source", "interventional", "compile"}
    with pytest.raises(KeyError):
        OPERATORS.get("nonexistent_op")


def test_listing_mentions_every_op():
    text = list_ops()
    for name, _op in OPERATORS.items():  # noqa: PERF102 — Registry, not a dict
        assert name in text


def test_recipe_reproduces_the_demo(tmp_path):
    config = tmp_path / "r.yaml"
    config.write_text(RECIPE.format(workdir=tmp_path / "wd"))
    ctx = run_recipe(config)
    validated = [u for u in ctx.units if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED]
    assert len(validated) == 6
    assert all(u.tier == EvidenceTier.MINIMAL for u in validated)
    assert set(ctx.exports) >= {"sft", "dpo", "memory", "regression"}
    assert (tmp_path / "wd" / "units.jsonl").exists()  # save_run persisted
