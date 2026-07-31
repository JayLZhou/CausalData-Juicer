# Changelog

## v0.1.0 — 2026-08-01

First complete release of the engine and its evidence program.

### Engine
- Five core abstractions (`Episode` / `Snapshot` / `Intervention` / `Outcome` /
  `CausalUnit`) with the six-level evidence ladder enforced on every surface.
- Paired counterfactual replay with determinism control branch, n× flip
  reproduction, ddmin minimal causal slicing, fork-time prep hooks and
  prefix re-execution from sparse checkpoints.
- Side-effect–graded tool execution (EXTERNAL never re-executed in replay);
  full LLM response disk-caching; cost ledgers throughout.
- Budget layer: control-branch memoization, early repro stop, pluggable
  acquisition policies (exhaustive / random / adaptive) under hard budgets.
- Provenance as per-dependency claims; selective revalidation under version
  events with staleness demotion.
- Verifiers: pytest and generic command (exit-code) — any executable workload.
- Candidate sources: fix tables, blind/test-aware fixer LLMs, temperature
  resampling, validation-in-the-loop refinement.
- Exports: SFT / DPO / memory / executable regression, TRL-SFT / TRL-DPO /
  verl parquet adapters, observational Import Mode (OBSERVED ceiling).

### Workload
- 52-task dependency-migration bench across 6 families (pydantic, numpy,
  sqlalchemy, click, networkx, pandas), every task certified
  pass-on-old / fail-on-new, hermetic and sealed.

### Evidence
- Claims A1–A14, B1–B5 lit; C1 recorded as an honest underpowered null.
  Flip reproducibility 100% in 11 configurations; six published
  data-construction strategies reproduced in 43–78 lines each.
