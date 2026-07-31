# Concepts

## Five objects

Everything in the engine is built from five schema objects
(`causeforge.sdk.schemas`):

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

Can CauseForge reproduce your data-construction method? Ask:

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

Four yeses ≈ a ~100-line case study. Note the boundary: CauseForge reproduces
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
