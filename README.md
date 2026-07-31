<div align="center">

# CausalData-Juicer

**A Budgeted Interventional Data Engine for Agent Improvement**

*One counterfactual execution machine. Any causal data-construction strategy in ~100 lines.*

[![CI](https://github.com/JayLZhou/CausalData-Juicer/actions/workflows/ci.yml/badge.svg)](https://github.com/JayLZhou/CausalData-Juicer/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-54%20passing-brightgreen.svg)](tests/)

[English] | [[中文](README_ZH.md)] · [Applications](#-application-scenarios) · [Operator Zoo](#-operator-zoo) · [Settings](#%EF%B8%8F-supported-settings) · [Why CausalData-Juicer](#-why-causaldata-juicer) · [How it works](#-how-it-works)

</div>

Experience systems store what agents *happened to try*;
**CausalData-Juicer actively acquires the causal experience agents *should learn from*** —
fork a recorded trajectory, apply an intervention, replay original and intervened
branches as a matched pair, verify the outcome **flips**, slice to the minimal
causal core, compile training-ready assets. An evidence tier rides on every row:

`Observed → Suggested → Counterfactual-Validated → Reproducible → Minimal → Training-Validated`

> **A running example.** Mira's coding agents failed 800 migration tickets
> the weekend pydantic 2 landed. The logs say what happened — not what would
> have worked. Asking a bigger model for fixes gives plausible patches, some
> quietly wrong, and nobody can tell which without running them.
> CausalData-Juicer forks the exact state before each wrong step, tries
> candidate corrections **for real**, keeps only those that verifiably flip
> the outcome, and stamps every row with its evidence tier, cost, and the
> dependency claims under which it stays valid — so the next upgrade
> revalidates exactly what it touches.

## 🎯 Application scenarios

| Scenario | You bring | You get |
|---|---|---|
| **Agent self-improvement** | your agent's failed trajectories + a replayable env | validated SFT/DPO correction pairs mined from your own failures — certified to flip outcomes, not just look plausible |
| **RL / preference-data engine** | tasks + verifier + any chat endpoint | step-level DPO pairs, PRM labels, tree credit — exported trainer-native (TRL, verl parquet) |
| **Agent regression testing & version evaluation** | a run directory | *executable* counterfactual suites: on every model/prompt/dependency upgrade, replay and check the flips still hold |
| **Dependency-migration / code-maintenance bots** | a repo + its test suite | failure→recovery memory units and correction pairs for real breaking changes (our certified 52-task bench domain) |
| **Structured-generation process supervision** (Text-to-SQL etc.) | queries + an executor | clause/segment-level criticality labels in both directions (see the CAPER case) |
| **Data freshness operations** | long-lived data assets + version events | provenance-driven selective revalidation: re-check only what a dependency change can touch, demote what went stale |
| **Agent memory / skill libraries** | failed + repaired episodes | failure→recovery units with evidence tiers, ready for retrieval |
| **Method research** | a new paper's data-construction idea | a same-day ~100-line reproduction under one metered roof — compare strategies at matched budgets |

## 🧩 Operator Zoo

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
| step-DPO, PRM, ATE-credit, tree-credit, clause-PRM | example-level compilers in [`examples/`](examples/) |

## ⚙️ Supported settings

| Dimension | Supported today |
|---|---|
| **Environments** | local filesystem sandbox; per-task virtualenv isolation with cross-interpreter bases (tested: py3.11 + py3.12 in one bench); content-addressed snapshots with checkpoint placement (`every` / `every_k:N` / `first`) |
| **Verifiers** | `PytestVerifier` (parsed counts) and `CommandVerifier` (any command, success = exit 0 — builds, `make test`, SQL runners, linters) |
| **Agents** | scripted policies and live LLM agents via any OpenAI-compatible endpoint (vLLM, commercial APIs); all responses disk-cached |
| **Models used in our runs** | Qwen2.5 7B / 14B / 32B-AWQ locally; any chat endpoint works |
| **Access tiers** | Import Mode (traces only, ceiling OBSERVED) → Tool Replay (tools + verifier) → Snapshot Mode (full engine) |
| **Side effects** | tools declare `PURE / IDEMPOTENT / REVERSIBLE / TRANSACTIONAL / EXTERNAL_SIDE_EFFECT`; external effects are dry-run mocked during replay, never re-executed |
| **Workload** | a 52-task dependency-migration bench (6 real breaking-change families), every task certified pass-on-old / fail-on-new, hermetic, sealed, anti-cheat verified |

## 🏆 Why CausalData-Juicer

| | Data-Juicer family | **CausalData-Juicer** |
|---|---|---|
| Input | corpora you already have | a replayable execution environment |
| Core act | operator transforms (filter/dedup/synthesize) | fork / intervene / paired counterfactual replay |
| Quality signal | heuristics & model scores (pool-level, observational) | verifier outcome **flips** (unit-level, interventional, reproduced) |
| Env in the loop | no | **yes — the defining axis** |
| Staleness | re-run the pipeline | provenance-driven *selective* revalidation |

Plus what no prompt-only system has: **executed feedback** (refinement sees its
attempt's real failing output), **negative controls in CI** (flaky environments
are rejected, not certified), **honest accounting** (every number pre-registered
in the [claims ledger](experiments/claims.md) — nulls included, on the front page).

## 🔬 How it works

Everything below fills one ten-line skeleton:

```python
episode, snapshots = collector.run_episode(task, workspace, policy)   # record
iv = Intervention(...)                                  # alternative action, any source
unit = replayer.paired_replay(episode, snapshots, iv)   # control + branch + n× repro
if unit.flipped:
    export(unit)          # -> SFT / DPO / PRM / memory / regression / verl / TRL
```

**The vision, implemented as a loop** — the system *decides which executions to
run*: [`Collector`](causal_data_juicer/runtime/collector.py) snapshots the workspace at
every step boundary while recording actions/observations/LLM calls → candidate
sources propose alternative actions → the replayer validates → slicing
minimizes → compilers materialize. Nothing is trusted because it looks
plausible; everything is trusted because it was **executed twice and compared**.

**Validation, concretely** ([`replay/replayer.py`](causal_data_juicer/causal_data_juicer/replay/replayer.py)):
restore the pre-step snapshot; run the **control branch** with the recorded
actions — its per-step observation digests and final outcome must match the
recording (environment drifted? the unit is *refused*, spend stops); run the
**intervened branch**; a flip means fail→pass; reproduce it n× from fresh
forks; ddmin re-validates the minimal atom set. Anti-cheat seals (test files
byte-identical) and CI negative controls guard the instrument itself.

**The budget, and why it exists** ([`acquisition/`](causal_data_juicer/causal_data_juicer/acquisition/)):
every token, second and dollar charges a `CostLedger` from line one; `Budget`
is a hard ceiling, not advice. The always-on mechanism layer (control-branch
memoization, early repro stop, full LLM caching) measured **26% replay savings
at identical output**; pluggable policies allocate the remaining spend —
measured to matter exactly when budgets are tight (+33% units at 30 replays)
and to vanish when they're not. Every unit carries its own acquisition cost, so
*cost-per-validated-unit* is a first-class, reportable number (~3s on our bench).

## 🚀 Quick start

```bash
git clone https://github.com/JayLZhou/CausalData-Juicer.git && cd CausalData-Juicer
python3 -m venv .venv && .venv/bin/pip install -e .

.venv/bin/python -m causal_data_juicer demo              # end-to-end loop, one command
.venv/bin/python -m causal_data_juicer regress runs/demo # replay exported counterfactual cases
.venv/bin/python -m pytest tests/
```

| Command | What it does |
|---|---|
| `demo` / `bench-build` | toy loop with kill-line report / certify the 52-task bench |
| `collect-depmig` | live agent collection; `--sources fixer,fixer-tests,resample`, `--refine-rounds N` |
| `acquire-eval` / `storage-bench` | budgeted policy curves / checkpoint placement trade-off |
| `revalidate` | selective revalidation under a dependency version event |
| `export` / `import-trace` | TRL-SFT / TRL-DPO / verl adapters / observational Import Mode |

## 📊 Measured results

| Claim | Result |
|---|---|
| Flip reproducibility (kill line ≥90%) | **100% across 11 configurations** (toy → live agents → cross-interpreter) |
| Control-branch digest match | **100%**, with CI-enforced negative controls |
| Mechanism-layer savings | **26%** fewer replays, identical output |
| Budgeted acquisition (295 candidates) | adaptive +33% @30 replays; converges when budget abounds |
| Selective revalidation (2 real version events) | **4.8× / 8.0×** cheaper, zero missed demotions |
| Checkpoint forking | **298×** vs from-scratch; byte-identical reconstruction |
| Source science | failure→data conversion 24/35; stochastic sources pierce deterministic-model ceilings |
| Training value (C1) | honest **underpowered null** at ~40 rows; re-test conditions logged |

## 🔁 Showcase: reproduce a paper's data engine before lunch

| Published strategy | Case study | Lines | Real output |
|---|---|---|---|
| MCTS → step-level DPO pairs | [`case_step_dpo.py`](examples/case_step_dpo.py) | 76 | 12 same-state preference pairs |
| Rollout-tree credit (Tree-GRPO/RTMC) | [`case_rollout_tree.py`](examples/case_rollout_tree.py) | 78 | executed trees + group-relative advantages |
| Counterfactual credit / ATE (CCPO) | [`case_credit_ate.py`](examples/case_credit_ate.py) | 53 | credit-annotated trajectories, offline |
| Process-reward labels | byproduct of `case_step_dpo.py` | — | 46 executed-branch PRM labels |
| HER-style relabeling | [`case_her_relabel.py`](examples/case_her_relabel.py) | 43 | achieved-goal rows, zero replay/LLM |
| **CAPER clause PRM** (arXiv:2606.03327, *June 2026*) | [`case_caper_clause_prm.py`](examples/case_caper_clause_prm.py) | 77 | clause criticality, both directions, **same-day repro** |

## 📚 Documentation & License

[Docs site](https://jaylzhou.github.io/CausalData-Juicer/) ·
[Tutorial](docs/tutorial.md) · [Concepts](docs/concepts.md) ·
[Design](docs/design.md) · [Bench spec](docs/bench-m15-spec.md) ·
[Claims ledger](experiments/claims.md) · [中文项目合同](README_ZH.md)

Apache-2.0.

```bibtex
@misc{causal_data_juicer2026,
  title  = {CausalData-Juicer: A Budgeted Interventional Data Engine for Agent Improvement},
  author = {Zhou, Yingli},
  year   = {2026},
  url    = {https://github.com/JayLZhou/CausalData-Juicer}
}
```

The name nods to [Data-Juicer](https://github.com/modelscope/data-juicer):
they refine the data you already have; we run the executions that create the
data you're missing — the interventional axis, upstream of the observational one.
