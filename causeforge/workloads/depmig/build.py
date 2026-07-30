"""Bench builder & validity certificate (spec §4, §7).

For every task, prove the bench itself is honest before any agent sees it:

  1. hermeticity scan on sealed test files;
  2. tests PASS in the family's old-pin env (test suite is correct);
  3. tests FAIL in the family's new-pin env (breaking change is real).

Envs are built once (network allowed here, never during episodes) and
their pip-freeze goes into the certificate for provenance.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from causeforge.runtime.envs import EnvManager, write_env_pointer
from causeforge.runtime.verifier import PytestVerifier
from causeforge.sdk.schemas import CostLedger
from causeforge.workloads.depmig.base import DepMigTask, scan_hermeticity


def enabled_families():
    from causeforge.workloads.depmig import (
        click_family,
        networkx_family,
        numpy_family,
        pydantic_family,
        sqlalchemy_family,
    )
    modules = [pydantic_family, numpy_family, sqlalchemy_family, click_family, networkx_family]
    return [(m.FAMILY, m.build_tasks()) for m in modules]


def all_tasks() -> list[DepMigTask]:
    return [t for _, tasks in enabled_families() for t in tasks]


def build_and_validate(env_root: Path, scratch: Path) -> dict:
    mgr = EnvManager(env_root)
    verifier = PytestVerifier(timeout=120)
    scratch = Path(scratch)
    results, ok = [], True

    for family, tasks in enabled_families():
        pythons = {
            "old": mgr.ensure(family.old_env()),
            "new": mgr.ensure(family.new_env()),
        }
        for task in tasks:
            violations = scan_hermeticity(task)
            row = {"task": task.id, "family": family.name, "tier": task.tier,
                   "hermetic": not violations, "violations": violations}
            for which, expect_pass in (("old", True), ("new", False)):
                ws = scratch / f"{task.id}-{which}"
                if ws.exists():
                    shutil.rmtree(ws)
                task.setup(ws)
                write_env_pointer(ws, pythons[which])
                outcome = verifier.evaluate(ws, CostLedger())
                row[f"{which}_pass"] = outcome.success
                row[f"{which}_detail"] = outcome.detail.splitlines()[-1] if outcome.detail else ""
            row["valid"] = row["hermetic"] and row["old_pass"] and not row["new_pass"]
            ok = ok and row["valid"]
            results.append(row)

    certificate = {
        "workload": "depmig-v1",
        "valid": ok,
        "tasks": results,
        "envs": {
            f"{family.name}-{which}": mgr.provenance(env)
            for family, _ in enabled_families()
            for which, env in (("old", family.old_env()), ("new", family.new_env()))
        },
    }
    return certificate


def print_certificate(cert: dict) -> None:
    print(f"depmig bench validity: {'OK' if cert['valid'] else 'INVALID'}")
    print(f"{'task':<18} {'tier':<4} {'hermetic':<8} {'old':<5} {'new':<5} valid")
    for row in cert["tasks"]:
        print(f"{row['task']:<18} T{row['tier']:<3} {str(row['hermetic']):<8} "
              f"{'pass' if row['old_pass'] else 'FAIL':<5} "
              f"{'PASS' if row['new_pass'] else 'fail':<5} "
              f"{'✓' if row['valid'] else '✗'}")


def save_certificate(cert: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cert, indent=2, ensure_ascii=False))
