"""Structure-level depmig bench tests (no env building — the full
pass-old/fail-new validation lives in `causal_data_juicer bench-build`'s
certificate, which is the bench's admission ticket)."""
from collections import Counter

from causal_data_juicer.workloads.depmig.base import scan_hermeticity
from causal_data_juicer.workloads.depmig.build import all_tasks, enabled_families


from causal_data_juicer.workloads.depmig import pandas_family

CORE = {"pydantic", "numpy", "sqlalchemy", "click", "networkx"}


def test_bench_shape():
    tasks = all_tasks()
    assert len(tasks) == len({t.id for t in tasks})  # unique ids
    families = Counter(t.family.name for t in tasks)
    assert set(families) >= CORE
    assert all(n >= 6 for n in families.values())
    if pandas_family.available():
        assert families["pandas"] >= 6


def test_tier_coverage_per_family():
    by_family: dict[str, Counter] = {}
    for t in all_tasks():
        by_family.setdefault(t.family.name, Counter())[t.tier] += 1
    for name, tiers in by_family.items():
        assert tiers[1] >= 1 and tiers[2] >= 1, name
        if name != "networkx":  # documented: no silent-semantics break found there
            assert tiers[3] >= 1, name


def test_all_tasks_hermetic():
    for task in all_tasks():
        assert scan_hermeticity(task) == []


def test_every_task_has_sealed_tests_and_prompt():
    for task in all_tasks():
        assert task.test_files(), task.id
        assert task.tests_digest()
        prompt = task.agent_prompt()
        assert "Do not modify test files" in prompt
        assert task.migration_points, task.id


def test_env_pins_are_exact():
    for family, _ in enabled_families():
        for pin in family.old_pins + family.new_pins:
            assert "==" in pin, pin
