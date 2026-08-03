# FAQ

**How is this different from just asking a strong LLM to fix my code?**
An LLM gives you plausible text. We *executed* a 32B model's suggestions on
our bench: several imported packages that weren't installed — they looked
right and crashed. Every unit here survived a controlled experiment instead:
a control branch reproduced the original failure, the intervened branch
flipped the outcome, the flip reproduced n times, the minimal cause was
isolated, and the cost was metered. See
[the full story](story-migration.md).

**What do I need to provide?**
Three things: a workspace (your files), a verifier (any command — exit 0 is
success), and an OpenAI-compatible endpoint URL. Import Mode needs only a
JSONL of traces. See [Getting started](getting-started.md).

**Do I need your bench?**
No. The bench is our evidence ground. Your entry points are `cdj run`
(your repo), `cdj import-trace` (your logs), or YAML recipes over your own
workload (`cdj process`).

**What if my agent solves the task?**
Success-mining kicks in: the fixing action is re-validated against an
identity control (a genuinely failing re-recording), so successes also
yield certified units.

**What if my environment is flaky?**
The determinism gate *refuses* to certify it — control-branch mismatch
returns the candidate as SUGGESTED and spends nothing further. CI negative
controls prove this behavior. Flakiness costs you coverage, never validity.

**Can the agent cheat by editing my tests?**
It tried (really — see the friction log). Files matching test patterns are
sealed: restored from the pristine baseline before *every* verification,
with attempts counted in the report.

**What model should I use for collection?**
Mid-tier. Measured: a 14B agent's failures were a strict subset of a 7B's —
weaker collectors produce a superset of learning material. Spend strength on
*fixers*, and pool diverse sources (our biggest coverage lever).

**Are the numbers on the front page real?**
Run `cdj verify-claims`. It re-collects the demo, re-validates the flips,
re-trips the negative controls, replays the exported counterfactuals, and
re-executes a committed replay pack byte-for-byte — on your machine. It
reports a three-state PASS/FAIL/SKIP scorecard (a skipped check is never
counted as passed; `--strict` makes skips fail) and explicitly lists the
ledger rows it cannot re-run offline — the GPU-hour-scale sweeps (budget
curves, source ladders, revalidation events, training pilots). For those,
the evidence is the pre-registered claims ledger plus archived run
directories under `experiments/results/`.

**Does training on this data actually help?**
Honest answer: unproven at our corpus size. Our matched-token pilot (~40
rows) showed an exact tie between validated and unvalidated data — recorded
as an underpowered null in the claims ledger with re-test conditions. The
engine's value claims don't depend on it.
