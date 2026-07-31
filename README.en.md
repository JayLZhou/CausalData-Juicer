# CauseForge

> **A Budgeted Interventional Data Engine for Agent Improvement**

Experience systems store what agents happened to try;
**CauseForge actively acquires the causal experience that agents should learn from.**

The engine decides which trajectory states to fork, what interventions to apply,
replays original and intervened branches as a matched pair, verifies whether the
outcome actually flips, slices the intervention down to its minimal causal core,
and compiles the result into training-ready assets — with an explicit evidence
tier riding on every single row:

`Observed → Suggested → Counterfactual-Validated → Reproducible → Minimal → Training-Validated`

| Output | Use |
|---|---|
| Minimal correction pairs | SFT / behavior cloning |
| Original/repaired branch pairs | DPO / preference learning |
| Failure-to-recovery units | Agent memory / skill libraries |
| Executable counterfactual cases | Regression testing / agent version evaluation |

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m causeforge demo              # end-to-end toy demo, one command
.venv/bin/python -m causeforge regress runs/demo # replay exported counterfactual cases
.venv/bin/python -m pytest tests/
```

More commands: `bench-build` (validate the dependency-migration bench),
`collect-depmig` (live LLM-agent collection), `acquire-eval` (budgeted
acquisition curves), `revalidate` (version-event maintenance),
`storage-bench` (checkpoint placement trade-off), `export` (TRL/verl
formats), `import-trace` (observational Import Mode).

## Measured results (see `experiments/claims.md` for provenance)

- **Flip reproducibility 100%** on live LLM-agent data (15/15 core bench,
  9/9 + 6/6 on the cross-interpreter pandas family) — kill line ≥ 90%.
- **Control-branch digest match rate 100%** (a number nobody else reports).
- Mechanism layer saves **26% of replays** for free (control memoization +
  early repro stop); policy layer is an honest null at 55-candidate scale.
- Selective revalidation under two real version events: **4.8× / 8.0×**
  fewer replays than full revalidation, with zero missed demotions.
- Checkpoint-everywhere forking is **298×** faster than from-scratch replay;
  content addressing shares **2.3×** across the trace DAG.
- Candidate-**source** diversity beats model strength: resampling the same 7B
  flips tasks the whole 7B+14B fixer pool missed (failure coverage 6/19 → 9/19).
- Two published-pipeline reproductions on the public API: tree-sampling →
  step-level DPO (**76 lines**), counterfactual step credit / ATE (**53 lines**,
  offline).

## Access tiers

| Tier | You provide | Operators available | Evidence ceiling |
|---|---|---|---|
| Import Mode | traces (JSONL) | observational + compile | OBSERVED |
| Tool Replay | tools + verifier | + local interventions | COUNTERFACTUAL-VALIDATED |
| Snapshot Mode | replayable env | everything | MINIMAL+ |

Hard rules baked into the executor: tools declare side-effect classes;
`EXTERNAL_SIDE_EFFECT` is never truly re-executed during replay (dry-run mock
only); LLM responses are fully disk-cached; every replay, token and dollar is
charged to a ledger from line one.

## Repository layout

```text
causeforge/
├── sdk/            # Episode / Snapshot / Intervention / Outcome, CausalUnit
├── runtime/        # collector, policies (scripted + live LLM), envs, importer
├── store/          # content-addressed blobs, trace DAG, checkpoint placement
├── replay/         # sandbox, recorded/paired replay, prefix re-execution
├── interventions/  # ActionReplace, ToolArgumentEdit (+ atom decomposition)
├── acquisition/    # screener, fixer sources, budget, policies, engine
├── slicing/        # ddmin minimal causal slicing
├── compiler/       # sft/dpo/memory/regression + TRL/verl adapters + observational
├── maintenance/    # provenance, selective revalidation
└── workloads/      # toy + depmig bench (36 tasks, 6 families, certified)
examples/           # published-pipeline reproductions (≤80 lines each)
experiments/        # claims.md — every claim wired to an experiment and a threshold
```

License: Apache-2.0. 中文版：[README.md](README.md)。
