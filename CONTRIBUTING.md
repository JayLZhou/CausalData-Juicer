# Contributing

## Ground rules (the project's contract)

1. **Evidence tiers are sacred.** Any new data path must carry
   `evidence_tier` on every row; weak evidence never masquerades as causal.
2. **Numbers come from experiments.** A claim lands in
   `experiments/claims.md` with a pre-registered threshold before its number
   is cited anywhere. Honest nulls are recorded, not hidden.
3. **Cost is accounted from line one.** Anything that spends tokens, seconds
   or dollars charges a `CostLedger`.
4. **External side effects are never re-executed in replay.** New tools must
   declare a `SideEffectClass`.

## Dev setup

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m pytest tests/     # must stay green
```

Bench work: `causeforge bench-build` must report a valid certificate
(pass-on-old / fail-on-new for every task) before a new task ships — probe
your breaking change empirically first; several "well-known" breaks turned
out to be shimmed.

## Good first contributions

- A new candidate source (implement `propose(episode) -> list[Intervention]`).
- A new verifier (implement `evaluate(workspace, ledger) -> Outcome`).
- A trace adapter for your agent framework (see
  `causeforge/runtime/import_trace.py` for the target schema).
- A case study reproducing a published data-construction method on the
  public API (≤100 lines; see `examples/`).
