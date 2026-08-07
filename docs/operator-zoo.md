# Operator Zoo

Operators extend Data-Juicer's observational signature to an interventional one:
`(Units, Env, Budget) → Units'`. Four categories form the algebra — observational
ops are free and can never raise a tier, source ops propose interventions,
interventional ops spend real execution budget and are the only way to climb the
evidence ladder, and compile ops materialize views.

Everything below is **registered and runnable in a YAML recipe** (`cdj process
--config recipe.yaml`) and listed by `cdj ops`. We deliberately do not mirror
Data-Juicer's 200+ text-cleaning operators: those answer an observational
question ("is this sample good?"), while every operator here answers an
interventional one ("would the outcome have changed?").

<!-- BEGIN GENERATED ZOO -->

**39 operators ship in this package**, in the four categories of the algebra. This table is generated from the registry by `scripts/gen_zoo_docs.py`; a test fails if it drifts from what `cdj ops` lists.

### `observational` — no environment, zero budget — can never raise a tier (16)

| operator | what it does | params |
|---|---|---|
| `attach_generation_provenance` | Reconnect executed units to the branches that proposed them. Without this the ladder has a hole: the selector hands the engine bare interventions, so a finished corpus cannot say which rows came from a model, which constraints they cleared beforehand, or which site was intervened on. Each matching unit gets ``provenance['generation']``, ``provenance['constraint_validation']`` and ``provenance['site']``. Units whose execution did not flip keep their execution-derived tier — passing a constraint filter is not evidence, and this operator never raises a tier | — |
| `collect_toy` | Collect the built-in toy workload (offline; also seeds the toy fix table as a candidate source) | — |
| `cost_report` | Ledger breakdown plus cost per validated unit into ctx.meta['cost'] | `out (optional path, relative to workdir)` |
| `counterfactual_validity_filter` | Composable verdicts on generated branches — hard constraints gate, soft scores rank, and rejections keep their provenance. Hard (all must hold, checked in order): intervention_fidelity the edit actually changed the named variable target_outcome_shift the branch is *aimed* at flipping the outcome invariant_preservation nothing outside the site moved schema_validity the resulting action is well-formed and executable by a registered tool Soft (recorded, never gating): minimality, semantic_proximity, fluency, diversity, verifier_confidence. Passing lifts a branch to **CONSTRAINT_VALIDATED and no further** — this operator never executes anything, so it cannot make a causal claim. A rejected branch is kept with ``failed_at`` and a reason, because the rejections are the training signal for the generator | `keep_rejected (default true), min_proximity (default 0.0, soft-only), drop_identical (default true)` |
| `coverage_report` | How much of the failure set got covered, by task and by tier, into ctx.meta['coverage'] | `out (optional path)` |
| `dag_stats` | Trace-DAG sharing statistics (unique trees, bytes saved) into ctx.meta['dag'] | — |
| `dedupe_units` | Drop units whose (episode, target step, effect) signature repeats — two fixes that flip the same failure the same way are one datum | — |
| `export_observational` | Behaviour-cloning and failure-log views straight from episodes — the OBSERVED-ceiling exports that need no replay at all | — |
| `filter_units` | Keep units matching a predicate | `min_tier (e.g. MINIMAL), flipped (bool), task_prefix (str), source (str). Unset params do not constrain` |
| `her_relabel` | Hindsight relabelling: a failed trajectory is optimal supervision for the goal it *did* reach. Pure re-reading of recorded episodes, so the rows carry the OBSERVED ceiling | `out (default exports/her_sft.jsonl)` |
| `import_traces` | Ingest external agent traces (Import Mode; OBSERVED ceiling) | `path` |
| `intervention_site_mapper` | Identify the variables in a trajectory that a ``do`` could act on, typed and annotated with what must stay fixed. Sites are read off recorded steps: tool arguments (``ToolArgument``), structured fields inside written artifacts (``StructuredField``), reasoning sentences (``Rationale``), retrieved blocks (``TextSpan``), subject-predicate-object statements (``SemanticTriple``), and the actions themselves (``AgentAction``). ``influence_score`` is an openly heuristic prior for ordering work — it is never evidence | `kinds (list, default all), rationale_paths (default ['thoughts.md']), context_paths (default ['context.md']), invariants (default ['task', 'repository', 'user_intent'])` |
| `load_run` | Load a previous run directory into the context | `path` |
| `replay_promotion_selector` | Decide which generated branches are worth real execution. Generation is cheap and unreliable; replay is expensive and decisive, so the budget should buy *information*, not volume. Branches are clustered by effect signature — two edits that change the same variable the same way are one experiment — and each cluster is scored value_i = P(flip)_i x novelty_i x coverage_i x uncertainty_i / cost_i then packed greedily by value density under ``budget``. A cluster's representative is queued first; ``sequential`` mode then re-scores the remaining clusters using the flip rate observed so far (a Beta-Bernoulli posterior over the cluster's strategy), and stops early once every remaining cluster falls below ``min_value`` — the branches that never reach a replay are recorded, not silently dropped. The output is a list of ReplayRequests in ctx.services['replay_requests'] and, for the interventional operators downstream, ctx.candidates | `budget (replays, default 20), sequential (default true), min_value (default 0.01), cost_per_replay (default 1.0), prior_flip (default 0.3)` |
| `sample_units` | Deterministically subsample units (stable across runs — the digest of the unit id decides) | `n (required), seed (default 0)` |
| `screen_failures` | Select failed episodes and gather deduped candidates from the context's sources | — |

### `source` — propose interventions (model cost, no execution) (10)

| operator | what it does | params |
|---|---|---|
| `clause_perturb` | Clause-level stress perturbations (CAPER semantics): patch one line of a written artifact with a supplied variant, so the verifier decides which clauses are critical and which are harmless | `path (required), patches (list of {line, text})` |
| `context_ablate` | Leave-one-document-out over an assembled context (ContextCite semantics): each candidate drops exactly one block, so a downstream reader that still succeeds proves the block was not load-bearing | `path (default context.md), separator (default '\n\n'), keep_min (default 1)` |
| `do_counterfactual_mapper` | ``do(Z_j = z_j')`` on identified sites, regenerating **only the declared descendants**. This is the difference between a counterfactual and a rewrite: the site says what changes and what must hold, so the edit touches one variable and the engine re-derives the downstream consequences by *executing* them. Unconstrained "rewrite the sample" prompting cannot make that distinction, which is why it is not offered here. Strategies (``strategy`` may be a list): mask_edit blank the site's value (the null intervention) retrieve_edit substitute a value from ``values`` / ``values_file`` rationale_edit truncate the reasoning at this sentence semantic_triple_edit swap the object of a subject-predicate-object descendant_regeneration ask a model for the new value, constrained to the site and its invariants (needs base_url/model) Every branch records its do(), the invariants it promises to preserve, and full generation provenance. Branches enter at SUGGESTED; the filter can raise them to CONSTRAINT_VALIDATED; only a paired replay goes higher | `strategy (default ['mask_edit']), values (list) or values_file, kinds (restrict site kinds), max_sites (default 0 = all), target_outcome (default 'success'), base_url, model, seed` |
| `fix_table` | Curated / cached fixes as a candidate source — the zero-cost way to replay a known set of corrections | `path (JSON {task_id: [{tool, args}, …]})` |
| `fixer_llm` | LLM fixer candidate source | `base_url, model, candidates (default 2), tests_by_task (optional)` |
| `message_ablate` | Multi-agent message credit: replace one teammate's message with a supplied alternative and let downstream agents re-react (needs `continuation_policy` at replay time to be meaningful) | `path (default inbox.md), replacements (list of strings, or a JSON file via replacements_file)` |
| `refine` | Validation-in-the-loop: revise the interventions that did NOT flip, conditioning on their own executed failure output. Requires units from a previous paired_replay | `base_url, model, rounds (default 1)` |
| `resample` | Temperature-resampling candidate source | `base_url, model, k (default 3), temperature (default 0.85)` |
| `thought_truncate` | Thought-anchor probing without a model: truncate a reasoning trace at each sentence boundary, so the earliest truncation that still flips marks the sentence carrying the counterfactual weight | `path (default thoughts.md)` |
| `tool_ablate` | Was this tool call necessary? Replace a step's action with a *pure* read of the same path, which keeps the trajectory plausible while removing the step's effect — downstream steps then re-react, and a run that still succeeds proves the call was not load-bearing | `tools (list of tool names to ablate, default ['write_file']), max_steps (default 0 = every matching step)` |

### `interventional` — execute the environment, spend budget, raise tiers (6)

| operator | what it does | params |
|---|---|---|
| `budget_screen` | Validate candidates under a hard budget with a pluggable acquisition policy — the "budgeted" half of the engine, exposed | `policy (exhaustive | random | adaptive, default adaptive), replays (budget, default 60), n_repro (default 3)` |
| `minimize` | ddmin-slice REPRODUCIBLE units to MINIMAL | — |
| `paired_replay` | Validate every candidate with paired counterfactual replay | `n_repro (default 3)` |
| `paired_replay_parallel` | paired_replay across a process pool — identical outputs, wall-clock divided by the worker count (the per-worker control caches duplicate some replays; cost_report will show it) | `workers (default 4), n_repro (default 3)` |
| `revalidate` | Selective revalidation under a dependency event: only units whose claims intersect the change are replayed, inside the NEW environment; survivors are re-stamped, casualties demoted | `family (required), python (required, interpreter of the new env), freeze (required, the new `pip freeze` text), mode (selective | full, default selective), n_repro (default 2)` |
| `stress_probe` | The stress direction: run each candidate as a single intervened branch against a *passing* episode and record whether it breaks the outcome — critical vs harmless, same machinery, opposite sign | — |

### `compile` — materialize views; tier-preserving (7)

| operator | what it does | params |
|---|---|---|
| `credit_ate` | Compile step-level counterfactual credit — ATE = P(success | do(a')) - P(success | a) — straight from stored paired outcomes. Offline: no replay, no model | `out (default exports/credit_ate.jsonl)` |
| `export_trl` | Trainer-native exports | `formats (default [trl-sft, trl-dpo, verl])` |
| `export_views` | Compile SFT / DPO / memory / regression views | — |
| `group_advantage` | Group-relative advantage per intervened branch — the data core of tree-based GRPO methods (TreeRL / Tree-GRPO / RTMC). Siblings are the units sharing a fork point; each one scores its own success minus the sibling-group mean. Offline: reads stored outcomes, executes nothing | `out (default exports/group_advantage.jsonl)` |
| `process_rewards` | Compile a process-reward view: one row per intervened atom, labelled by whether it was necessary (critical) or not (harmless) — the clause-PRM / step-PRM shape | `out (default exports/process_rewards.jsonl)` |
| `report` | Write the human-readable report for this recipe run (terminal text and optional HTML), so a recipe ends with something a person can read | `html (bool, default false)` |
| `save_run` | Persist the context as a run directory (episodes/snapshots/units) | `none (uses the recipe workdir)` |

<!-- END GENERATED ZOO -->

## Under the hood

The classes and functions these operators wrap, for readers who want the
Python API rather than the recipe vocabulary:

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

