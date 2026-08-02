# Concepts

## Five objects

Everything in the engine is built from five schema objects
(`causal_data_juicer.sdk.schemas`):

| Object | What it is |
|---|---|
| `Episode` | the recording: per-step actions, observations, cached LLM interactions |
| `Snapshot` | filesystem + declared state at a step boundary (content-addressed, restorable) |
| `Intervention` | a modification of one step: replace the action, or patch arguments — patches decompose into atoms for slicing |
| `Outcome` | the verifier's verdict |
| `CausalUnit` | the terminal asset: *this change flips this outcome, reproducibly* — evidence-tiered, provenance-stamped, cost-accounted |

And one call does the work: `Replayer.paired_replay(episode, snapshots,
intervention)` — restore the snapshot, prove the control branch still
reproduces the recorded outcome, execute the intervened branch, reproduce the
flip n times.

## The evidence ladder

```
OBSERVED                  it appeared in a trace
SUGGESTED                 a source proposed it (or validation refused it)
COUNTERFACTUAL_VALIDATED  one paired replay confirmed the flip
REPRODUCIBLE              n/n independent forks all flip
MINIMAL                   ddmin-sliced and re-validated
TRAINING_VALIDATED        downstream training gain demonstrated
```

Weak evidence can never masquerade as strong: every API surface and every
exported row carries the tier, and access tiers enforce ceilings (Import Mode
data cannot exceed OBSERVED).

## The four-question fit test

Can CausalData-Juicer reproduce your data-construction method? Ask:

1. **Does state fit in a snapshot?** Filesystem + declared state: yes.
   Mid-flight processes, remote service state: no.
2. **Is there a swappable action?** Writing files, editing arguments,
   perturbing clauses: yes.
3. **Is execution (near-)deterministic?** A determinism gate *rejects* flaky
   environments instead of emitting false certificates (CI-enforced negative
   controls prove it).
4. **Is there an automatic verifier?** Tests or execution comparison: yes.
   Any command works (`CommandVerifier`, success = exit 0). Human or LLM
   judges can plug in, but the evidence tier stays lower.

Four yeses ≈ a ~100-line case study. Note the boundary: CausalData-Juicer reproduces
papers' *data engines*, not their gradient updates — outputs export straight
into TRL/verl for training.

## Load-bearing constraints

- **Fork only at step boundaries.** No CRIU, no mid-process promises.
- **Side-effect-graded execution.** Tools declare
  `PURE / IDEMPOTENT / REVERSIBLE / TRANSACTIONAL / EXTERNAL_SIDE_EFFECT`;
  external effects are mocked during replay, never re-executed.
- **Recorded replay first.** LLM responses are fully disk-cached; live
  sampling is reserved for deliberately stochastic candidate sources.
- **Cost accounting from line one.** Tokens, seconds, dollars — ledgers
  everywhere; budgets are hard ceilings, not suggestions.

## Supported settings

| Dimension | Supported today |
|---|---|
| **Environments** | local filesystem sandbox; per-task virtualenv isolation with cross-interpreter bases (tested: py3.11 + py3.12 in one bench); content-addressed snapshots with checkpoint placement (`every` / `every_k:N` / `first`) |
| **Verifiers** | `PytestVerifier` (parsed counts) and `CommandVerifier` (any command, success = exit 0 — builds, `make test`, SQL runners, linters) |
| **Agents** | scripted policies and live LLM agents via any OpenAI-compatible endpoint (vLLM, commercial APIs); all responses disk-cached |
| **Models used in our runs** | Qwen2.5 7B / 14B / 32B-AWQ locally; any chat endpoint works |
| **Access tiers** | Import Mode (traces only, ceiling OBSERVED) → Tool Replay (tools + verifier) → Snapshot Mode (full engine) |
| **Side effects** | tools declare `PURE / IDEMPOTENT / REVERSIBLE / TRANSACTIONAL / EXTERNAL_SIDE_EFFECT`; external effects are dry-run mocked during replay, never re-executed |
| **Workload** | a 52-task dependency-migration bench (6 real breaking-change families), every task certified pass-on-old / fail-on-new, hermetic, sealed, anti-cheat verified |


## How it works, concretely

Everything below fills one ten-line skeleton:

```python
episode, snapshots = collector.run_episode(task, workspace, policy)   # record
iv = Intervention(...)                                  # alternative action, any source
unit = replayer.paired_replay(episode, snapshots, iv)   # control + branch + n× repro
if unit.flipped:
    export(unit)          # -> SFT / DPO / PRM / memory / regression / verl / TRL
```

**The vision, implemented as a loop** — the system *decides which executions to
run*: [`Collector`](https://github.com/JayLZhou/CausalData-Juicer/blob/main/causal_data_juicer/runtime/collector.py) snapshots the workspace at
every step boundary while recording actions/observations/LLM calls → candidate
sources propose alternative actions → the replayer validates → slicing
minimizes → compilers materialize. Nothing is trusted because it looks
plausible; everything is trusted because it was **executed twice and compared**.

**Validation, concretely** ([`replay/replayer.py`](https://github.com/JayLZhou/CausalData-Juicer/blob/main/causal_data_juicer/causal_data_juicer/replay/replayer.py)):
restore the pre-step snapshot; run the **control branch** with the recorded
actions — its per-step observation digests and final outcome must match the
recording (environment drifted? the unit is *refused*, spend stops); run the
**intervened branch**; a flip means fail→pass; reproduce it n× from fresh
forks; ddmin re-validates the minimal atom set. Anti-cheat seals (test files
byte-identical) and CI negative controls guard the instrument itself.

**The budget, and why it exists** ([`acquisition/`](https://github.com/JayLZhou/CausalData-Juicer/blob/main/causal_data_juicer/causal_data_juicer/acquisition/)):
every token, second and dollar charges a `CostLedger` from line one; `Budget`
is a hard ceiling, not advice. The always-on mechanism layer (control-branch
memoization, early repro stop, full LLM caching) measured **26% replay savings
at identical output**; pluggable policies allocate the remaining spend —
measured to matter exactly when budgets are tight (+33% units at 30 replays)
and to vanish when they're not. Every unit carries its own acquisition cost, so
*cost-per-validated-unit* is a first-class, reportable number (~3s on our bench).

