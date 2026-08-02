# Operator Zoo


Operators extend Data-Juicer's observational signature to an interventional one:
`(Units, Env, Budget) → Units'`. Three classes form a complete algebra —
observational ops are free, interventional ops spend real execution budget and
are the only way to climb the evidence ladder, compile ops materialize views.

### Observational (no env, zero budget, ceiling ≤ SUGGESTED)

| Operator | Module | What it does |
|---|---|---|
| `Screener` | `acquisition/screener.py` | select failed episodes, dedupe candidates by effect signature |
| `load_generic_traces` | `runtime/import_trace.py` | ingest external agent traces (Import Mode) |
| `compile_bc_sft` / `compile_failure_log` | `compiler/observational.py` | behavior cloning from successes / failure logs, OBSERVED-stamped |
| `dag_stats` | `store/dag.py` | shared-prefix trace-DAG sharing statistics |
| HER relabel | `examples/case_her_relabel.py` | failures → supervision for the goal they *did* achieve |

### Candidate sources (propose interventions; LLM cost, no execution)

| Operator | Module | Coverage character |
|---|---|---|
| `TableFixSource` | `acquisition/screener.py` | curated / cached fix tables |
| `FixerLLMSource` | `acquisition/fixer.py` | blind LLM fixer (sees failure output) |
| `FixerLLMSource(tests_by_task=…)` | `acquisition/fixer.py` | test-aware fixer — reads the sealed spec |
| `ResampleSource` | `acquisition/resample.py` | temperature resampling of the policy itself — pierces deterministic-model ceilings |
| `propose_refinement` | `acquisition/fixer.py` | validation-in-the-loop: revises against its own *executed* failure |

### Interventional (need env, spend budget, raise evidence tiers)

| Operator | Module | Tier effect |
|---|---|---|
| `Replayer.paired_replay` | `replay/replayer.py` | SUGGESTED → COUNTERFACTUAL-VALIDATED → REPRODUCIBLE |
| `Replayer.recorded_replay` | `replay/replayer.py` | determinism control (digest-matched) |
| `Replayer.intervened_flip` | `replay/replayer.py` | single-branch probe (slicing, stress direction) |
| `minimize_unit` (ddmin) | `slicing/ddmin.py` | REPRODUCIBLE → MINIMAL over intervention atoms |
| `Replayer.fork_at` | `replay/replayer.py` | fork anywhere from sparse checkpoints (prefix re-execution) |
| `revalidate` | `maintenance/revalidate.py` | version events: confirm & re-stamp, or demote stale units |
| `AcquisitionEngine.run` | `acquisition/engine.py` | budgeted scheduling of all of the above |

Intervention types: `ActionReplace` (swap the step's tool call) and
`ToolArgumentEdit` (`set` whole values or `patch_lines` — line atoms are what
slicing minimizes over; a SQL clause, a config line, a code hunk).

### Compile (zero budget, tier-preserving)

| Operator | Output |
|---|---|
| `compile_sft` / `compile_dpo` / `compile_memory` / `compile_regression` | minimal correction pairs / preference pairs / failure→recovery units / **executable** counterfactual test suites |
| `export_trl_sft` / `export_trl_dpo` / `export_verl` | TRL messages / TRL DPO / verl parquet, trainer-native |
| step-DPO, PRM, ATE-credit, tree-credit, clause-PRM | example-level compilers in [`examples/`](https://github.com/JayLZhou/CausalData-Juicer/blob/main/examples/) |

