#!/usr/bin/env bash
# Every CI gate, in CI order, runnable locally. Run this before claiming a
# commit is green — this file exists because a commit message once said
# "all gates pre-verified" when `ruff format --check` had been invalidated
# by a later edit in the same batch.
#
#   scripts/gates.sh          # lint, types, tests, coverage
#   scripts/gates.sh --full   # + build, twine, clean-wheel smoke, docs, audit
set -euo pipefail

PY=${PY:-.venv/bin/python}
BIN=$(dirname "$PY")
SEC='*/runtime/paths.py,*/runtime/context.py,*/runtime/rundir.py,*/store/blob.py,*/runtime/exec_backend.py,*/verify_claims.py,*/runtime/llm.py'

step() { printf '\n=== %s\n' "$1"; }

step "ruff check";        "$BIN/ruff" check causal_data_juicer tests examples
step "ruff format";       "$BIN/ruff" format --check causal_data_juicer tests examples
step "mypy";              "$BIN/mypy" causal_data_juicer
step "pytest + coverage"; "$PY" -m coverage run -m pytest tests/ -q
step "coverage (overall ratchet)"; "$PY" -m coverage report --fail-under=60
step "coverage (security boundary)"
"$PY" -m coverage report --fail-under=90 --include="$SEC"

if [[ "${1:-}" == "--full" ]]; then
  step "build";  rm -rf dist; "$PY" -m build
  step "twine";  "$BIN/twine" check dist/*
  step "clean-wheel smoke"
  rm -rf /tmp/cdj-clean && "$PY" -m venv /tmp/cdj-clean
  /tmp/cdj-clean/bin/pip install -q dist/*.whl
  (cd /tmp && /tmp/cdj-clean/bin/cdj demo --out /tmp/cdj-ci-demo --repro 2 \
     | grep "FLIP REPRO")
  step "mkdocs --strict"; "$BIN/mkdocs" build --strict
  step "pip-audit";       "$BIN/pip-audit" --skip-editable
fi

printf '\nall gates passed\n'
