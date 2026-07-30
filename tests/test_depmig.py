"""Structure-level depmig bench tests (no env building — the full
pass-old/fail-new validation lives in `causeforge bench-build`'s
certificate, which is the bench's admission ticket)."""
from collections import Counter

from causeforge.workloads.depmig.base import scan_hermeticity
from causeforge.workloads.depmig.build import all_tasks, enabled_families


def test_bench_shape():
    tasks = all_tasks()
    assert len(tasks) == 30
    assert len({t.id for t in tasks}) == 30
    families = Counter(t.family.name for t in tasks)
    assert set(families) == {"pydantic", "numpy", "sqlalchemy", "click", "networkx"}
    assert all(n == 6 for n in families.values())


def test_tier_distribution():
    tiers = Counter(t.tier for t in all_tasks())
    assert tiers[1] == 10
    assert tiers[2] == 16
    assert tiers[3] == 4  # networkx has no T3 (documented in its module)


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
