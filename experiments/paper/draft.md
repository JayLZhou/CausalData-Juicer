# CausalData-Juicer: A Budgeted Interventional Data Engine for Agent Improvement

> Draft v0.1 — all numbers trace to `experiments/claims.md` rows (cited as
> [A1]…[C1]); no number appears here without a pre-registered threshold there.

## Abstract

Agents generate abundant trajectories, but raw traces are observational:
single-armed, confounded, and quick to go stale under model, prompt, tool and
dependency upgrades. Existing experience systems process logs that *happened
to be produced*; improving an agent requires knowing what *would have
happened* under a different action. We present **CausalData-Juicer**, a data
engine that actively decides which executions to run: it forks recorded
trajectories at step boundaries, applies candidate interventions, replays
original and intervened branches as a matched pair, certifies outcome
**flips**, slices interventions to their minimal causal core, and compiles
evidence-tiered training assets. The engine extends the observational
operator algebra of data-processing systems with an interventional signature,
`(Units, Env, Budget) → Units'`, under a six-level evidence ladder that every
API surface and exported row must carry. On a doubly-certified 52-task
dependency-migration bench with live LLM agents, flip decisions reproduce at
**100% across 11 configurations**, guarded by CI-enforced negative controls
that reject nondeterministic environments. The budget layer saves **26%** of
replays at identical output; selective revalidation under two real dependency
events costs **4.8–8.0×** less than full revalidation with zero missed
demotions; checkpointed forking is **298×** faster than from-scratch replay.
Beyond the engine, budgeted acquisition at scale yields transferable
findings: candidate-*source* diversity dominates model strength on most
failures, while a cheap stochastic source pierces a ceiling that an entire
deterministic prompt-fidelity ladder could not. Six published
data-construction strategies — from MCTS-style step-DPO pairs to a
June-2026 clause-level PRM method — are each reproduced on the public API in
43–78 lines, one of them same-day. We release the engine, the bench, and a
claims ledger in which every number, including an honest underpowered null
on downstream training value, is pre-registered.

## 0 A running example

Counterfactual data construction has quietly become the workhorse of
LLM/agent improvement across domains. Math and reasoning pipelines branch
solution steps and keep the divergences (MCTS-derived step-level DPO pairs,
process-reward datasets). Agent RL methods sample rollout trees for
group-relative advantages (TreeRL, Tree-GRPO, ARPO) or estimate per-step
counterfactual credit (CCPO's ATE, RTMC, AT2PO). Code-repair agents mine
patch-vs-outcome pairs; Text-to-SQL systems perturb clauses against an
executor (CAPER); hindsight relabeling recycles failures into supervision;
RFT platforms wire experience buffers into training (Trinity-RFT). Different
tasks, same underlying act: *run an alternative and compare outcomes*. The
demand is everywhere — what is missing is shared machinery that makes those
comparisons valid, affordable, and durable. A concrete story shows why that
machinery is the hard part.

Mira maintains a fleet of coding agents that keep her company's Python
services on current dependencies. Over one weekend, pydantic 2 lands and her
7B agent fails 800 migration tickets. The logs are a mountain of *what
happened*; nothing in them says *what would have worked*. Her first instinct
— ask a bigger model for fixes and fine-tune on its answers — produces
plausible-looking patches: some right, some quietly wrong (one "fix" imports
a package that isn't installed), and nobody can tell which without running
them. Three weeks later a minor upgrade lands and silently invalidates a
third of whatever she trained on.

What Mira needs is not more logs and not more plausible text. She needs a
machine that takes each failure, forks the exact state before the wrong
step, tries candidate corrections **for real**, keeps only those that
verifiably flip the outcome — reproducibly — and then stands behind that
data: stamping every row with its evidence level, its cost, and the
dependency claims under which it remains valid, so the next upgrade
revalidates precisely what it touches and demotes what went stale. That
machine is this paper.

## 1 Introduction

The data engines behind recent agent-improvement methods share a loop:
branch a trajectory, roll out an alternative, compare outcomes, derive a
training signal. MCTS-derived step-level DPO pairs, tree-structured group
advantages, counterfactual credit estimates, process-reward labels and
hindsight relabeling all instantiate it — and each paper hand-builds the
loop again: its own forking, its own replay, its own bookkeeping, its own
notion of when a comparison is trustworthy.

We argue this loop deserves to be a system, and that building it as one
surfaces problems the per-paper implementations silently skip:

- **When is a counterfactual comparison valid?** If the environment drifted
  between recording and replay, the comparison is meaningless. We make the
  check explicit: a determinism control branch must reproduce the recorded
  observations and outcome before an intervened branch may be credited, and
  negative controls in CI prove the gate rejects environments with hidden
  state (§4.1, [A13]).
- **What did the comparison cost?** Interventional data is bought with real
  execution. Every token, second and dollar charges a ledger from line one;
  budgets are hard ceilings; cost-per-validated-unit is a first-class metric
  (§4.2, [A5]).
- **When does the data expire?** Validated counterfactuals are claims about
  an environment. We stamp each unit with per-dependency claims and
  selectively revalidate exactly the units a version event can touch,
  demoting what went stale (§4.4, [A8]).
- **How strong is the evidence?** A six-level ladder — Observed → Suggested →
  Counterfactual-Validated → Reproducible → Minimal → Training-Validated —
  rides on every row; access tiers enforce ceilings so imported traces can
  never masquerade as causal (§3).

**Contributions.**
**(C1)** An operator algebra extending observational data processing with an
interventional signature and an enforced evidence ladder (§3).
**(C2)** The engine: paired counterfactual replay with a determinism gate,
an always-on budget mechanism layer with pluggable acquisition policies,
content-addressed snapshot storage with checkpoint placement, and
provenance-driven selective revalidation — each with measured numbers (§4).
**(C3)** Empirical acquisition science from ~300 validated interventions:
how coverage scales with source diversity, prompt fidelity, stochasticity
and agent capability (§6).
**(C4)** An expressiveness evaluation: six published data-construction
strategies reproduced on the public API in 43–78 lines each, including a
same-day reproduction of a June-2026 method (§7).
**(C5)** A bench-construction methodology — dual certification
(pass-on-old / fail-on-new), hermeticity scanning, anti-cheat seals — plus
the observation that several famous "breaking changes" do not in fact break
(§5).

We also report what did *not* work: a matched-token training pilot on ~40
correction pairs shows no detectable difference between replay-validated and
unvalidated data (§8). The claims ledger that governs this paper
pre-registers thresholds for every number and records nulls beside wins.

## 2 Related work

**Observational data processing.** Data-Juicer and its descendants (DJ 2.0,
DJ Sandbox, Trinity-RFT) organize corpus refinement as operator pipelines:
`Dataset → Dataset` transforms with pool-level quality signals. We sit
upstream on an orthogonal axis: our operators may execute the environment,
and our quality signal is a unit-level verifier flip, reproduced. Trinity-RFT
connects experience buffers to RFT loops but replays what was logged;
none of the family validates counterfactuals or versions its data's validity.

**Branch-and-rollout data construction.** Methods that mine training signal
from alternative rollouts — MCTS→step-DPO, TreeRL/Tree-GRPO, rollout-tree
credit (RTMC, AT2PO), SCM/ATE-based credit (CCPO), CriticSearch, clause-level
process supervision (CAPER) — are the family whose common loop we systematize;
§7 reproduces six members on our API.

**Replay and slicing.** Our determinism gate adapts record/replay ideas to
LLM-agent traces (responses are cached, tools are side-effect-graded);
minimal-intervention slicing is delta debugging (ddmin) applied to
intervention atoms rather than program inputs. Hindsight relabeling (HER)
appears in our algebra as a purely observational operator.

## 3 Abstractions (C1)

Five schema objects carry the system. An **Episode** records per-step actions,
observations (with normalized digests) and cached LLM interactions. A
**Snapshot** is filesystem-plus-declared-state at a step boundary,
content-addressed so identical states share storage. An **Intervention**
modifies one step: replace the tool call, or edit its arguments — argument
edits decompose into atoms (per-line patches), the currency of slicing. An
**Outcome** is a verifier verdict. A **CausalUnit** is the terminal asset:
*this intervention flips this outcome, reproducibly*, with tier, provenance,
and its own acquisition cost attached.

Operators form three classes. *Observational* operators (screening,
signature-dedup, trace import, hindsight relabeling, behavior-cloning
compilation) need no environment, cost nothing, and are capped at the
Suggested/Observed tiers. *Interventional* operators (paired replay, repro
runs, slicing, revalidation) execute the environment, spend budget, and are
the only way up the ladder. *Compile* operators materialize views (SFT, DPO,
PRM, memory, executable regression suites, TRL/verl exports) and preserve
tiers. Access tiers are subsets of the algebra with enforced evidence
ceilings: Import Mode (traces only → Observed), Tool Replay, and Snapshot
Mode (full engine).

Hard rules are enforced in the executor, not in documentation: tools declare
side-effect classes and `EXTERNAL_SIDE_EFFECT` calls are dry-run mocked
during replay; LLM responses are disk-cached and never re-queried during
replay; forking happens only at step boundaries (no process snapshots).

## 4 Engine (C2)

### 4.1 Paired counterfactual replay and the determinism gate

To validate a candidate intervention at step *k*: restore the pre-*k*
snapshot; run the **control branch** — the recorded actions — and require
per-step observation digests and the final outcome signature to match the
recording; then run the **intervened branch**; a flip (fail→pass) must then
reproduce across *n* fresh forks; a ddmin pass re-validates the minimal atom
subset. Control mismatch refuses the unit *before* any intervened spend.

Observation digests are deliberately **outcome-grained**: `run_pytest`
digests its pass/fail summary, not log bytes, so timestamps in tracebacks
cannot poison determinism, while flaky *verdicts* still trip the gate. Two
CI-enforced negative controls pin this down [A13]: an environment with
hidden state outside the snapshot boundary is rejected (control mismatch,
tier stays Suggested, zero intervened spend); content noise with stable
verdicts validates normally.

Across all live configurations — two agent models, three fixer settings,
temperature sources, a cross-interpreter family — the gate reports **100%
control digest match** and flip decisions reproduce **100%** (kill-line
threshold ≥90%, 11 configurations, 18/18 to 87/87 per run) [A1, A9].

### 4.2 The budget layer

Acquisition cost has two layers. The **mechanism layer** is always on:
control-branch memoization per fork point, early termination of repro runs
at the first non-flip, and full LLM response caching. An ablation on a pooled
55-candidate set shows 137→101 replays (−26%) at byte-identical output [A7].
The **policy layer** schedules which candidates to validate under a hard
`Budget`. On a 295-candidate heterogeneous pool, an adaptive policy
(episode-breadth first, family-level UCB, source diversity) leads random and
exhaustive baselines at tight budgets (+33% validated units at 30 replays)
and converges with them when budget abounds [A7] — the optimizer matters
exactly when budgets bind. Cost-per-validated-unit on our bench is ~3s of
machine time at zero API dollars (local vLLM) [A5].

### 4.3 Storage and forking

The content-addressed store makes the trace DAG implicit: on a live
collection run, 186 snapshot references collapse to 81 unique trees (2.3×
sharing, 56.6% bytes saved). Checkpoint placement policies trade storage for
fork latency; forking from per-step checkpoints is **298×** faster than
replaying from scratch, and sparse-checkpoint forks reconstruct
byte-identical trees (digest equality is asserted inside the benchmark)
[A6].

### 4.4 Freshness: selective revalidation

Each unit's provenance records *dependency claims* — per-family environment
freezes, tool-registry and workload digests. A version event compares its
scope against each unit's claims; only intersecting units revalidate, inside
the *new* environment via a fork-time pointer override. Two real events on a
9-unit corpus [A8]: upgrading pydantic 2.7.4→2.11.7 revalidates 2 units in 5
replays vs 24 for full revalidation (**4.8×**), all fixes surviving; rolling
click 8.1.7 back to 7.1.2 costs 2 vs 16 replays (**8.0×**) and correctly
demotes all four click units — with reason `control-drift`: the rollback
makes the original bugs vanish, so the counterfactual pairs themselves are
stale, a failure class invisible to any system that does not re-run its
control branch. Demotion sets agree between selective and full modes in both
events (zero missed demotions).

## 5 A doubly-certified bench (C5)

Claims about flip validity need a workload where ground truth is knowable.
We build a 52-task dependency-migration bench: six families of real breaking
changes (pydantic 1→2, numpy 1→2, sqlalchemy 1.4→2.0, click 7→8,
networkx 2→3, pandas 1.5→2.2 on a second interpreter), each task a small
repo written against the old pin, executed against the new pin, with sealed
hermetic tests (no network, no clocks, no unseeded randomness) and
difficulty tiers (mechanical / multi-point / silent-semantic).

Every task carries a **dual certificate**: its tests must pass under the old
pin and fail under the new one, rebuilt from frozen environments. The
certificate caught five would-be tasks whose famous breaks are in fact
shims: pydantic keeps `GenericModel` and SQLAlchemy 2.0 keeps `Query.get` as
warnings, `np.trapz` survives 2.0, and click changed quote style and
underscore-name handling before 7.1. Migration benches built without
bidirectional certification will contain vacuous tasks. Anti-cheat seals
(byte-identical sealed tests, env-pointer integrity) are enforced at
collection time; live agents produced zero seal violations across all runs.

## 6 Acquisition science (C3)

Live collection (Qwen2.5-7B agent; 35/52 tasks failed) with candidate
sources measured in isolation yields findings that transfer beyond our
bench:

**Source diversity beats model strength — until it doesn't.** On core tasks,
a 7B and a 14B fixer flip largely disjoint task sets (4 vs 3, overlap 1);
their union beats either. On harder multi-point tasks the 14B strictly
dominates (6 ⊃ 1). Coverage strategy: pool cheap diverse sources for the
easy mass, spend fidelity on the hard tail [A10].

**Stochasticity is a coverage mechanism.** Temperature resampling of the
*same* 7B flips tasks the entire 7B+14B fixer pool missed, and later
cracked the NEP-50 silent-overflow task that had resisted a full
deterministic fidelity ladder — blind fixer, test-aware fixer, and
validation-in-the-loop refinement at 14B [A12]. Dense resampling (k=8, 88
draws) on the remaining holdouts produced zero flips, cleanly separating
sampling-starved failures from method-limited ones [A14].

**Executed feedback is a distinct fidelity rung.** Refinement — showing the
fixer its own attempt's *executed* failing output — flipped 4 further tasks
in 60 attempts, including tasks no one-shot source covered. This feedback
only exists because a replay engine ran the attempt [A12].

**Failure profiles nest by capability.** A 14B agent solves 27/36 tasks to
the 7B's 13/36, and its failure set is a strict subset of the 7B's —
supporting mid-tier collectors: weaker agents' failures subsume stronger
agents' [A11].

End to end, the source portfolio converts **24/35** failed tasks into
validated units (59 distinct units), with the uncovered tail itemized
(silent-formatting T3s dominate).

## 7 Expressiveness (C4)

Six published data-construction strategies, each a filling of the same
ten-line skeleton on the public API, each executed for real:

| Strategy | Lines | Output produced |
|---|---|---|
| MCTS → step-level DPO pairs | 76 | 12 same-state preference pairs |
| Rollout-tree credit (Tree-GRPO family) | 78 | depth-2 executed trees, group-relative advantages; level 2 conditions on executed failures |
| Counterfactual credit / ATE (CCPO) | 53 | 9 credit-annotated trajectories, compiled offline |
| Process-reward labels | — | 46 executed-branch PRM rows (byproduct) |
| HER relabeling | 43 | 34 achieved-goal rows; zero replay, zero LLM, Observed-capped |
| CAPER clause-level PRM (arXiv:2606.03327) | 77 | clause criticality **in both directions**, reproduced same-day |

The CAPER case doubles as the first demonstration of the **stress
direction**: perturbing a *correct* SQL query's clauses labels 3 of 6
perturbations critical and 3 harmless, exactly matching SQL semantics —
repair (fail→pass) and stress (pass→fail) are the same machinery with the
sign flipped.

## 8 Training-value pilot: an honest null

Does replay validation make correction pairs *train* better than the same
distribution unvalidated? Matched-token arms from the same fixer proposals
(validated: 43 rows; unvalidated: 38 rows), identical LoRA recipe and seed,
cross-family holdout. Result: base 6/16, validated 5/16, unvalidated 5/16
on held-out tasks — 15/16 tasks identical across all arms; the arms tie
exactly [C1]. At ~40 rows this is below any detection threshold; we
pre-registered the kill condition (validated *losing* to unvalidated), which
did not trigger. We publish the null, the power analysis, and the re-test
conditions (≥10× corpus or task-targeted evaluation) rather than a favorable
subset.

## 9 Limitations

The bench core is Python (the SQL case study only partially offsets this);
snapshots exclude live processes (no CRIU); training value remains
undemonstrated at current corpus scale; adoption evidence is forthcoming
with release. The engine's numbers are measured on one node — distributed
collection is future work.

## 10 Conclusion

Treating "branch → execute → compare → label" as a system rather than a
per-paper ritual buys three things at once: validity (a gate that refuses
bad comparisons, with negative controls), economics (budgets, mechanisms
and policies with measured savings), and longevity (provenance-driven
freshness). The same investment makes new methods cheap: the marginal cost
of reproducing a published data engine dropped, for us, to under a hundred
lines and sometimes under a day.
