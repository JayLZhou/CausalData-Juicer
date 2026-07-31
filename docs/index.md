# CausalData-Juicer

![Overview](assets/overview.png)

**A budgeted interventional data engine for agent improvement.**
*One counterfactual execution machine — any causal data-construction strategy in ~100 lines.*

Experience systems store what agents *happened to try*; CausalData-Juicer actively
acquires the causal experience agents *should learn from*: fork a recorded
trajectory, apply an intervention, replay original and intervened branches as
a matched pair, verify the outcome **flips**, slice the intervention to its
minimal causal core, and compile training-ready assets — with an evidence tier
on every row:

`Observed → Suggested → Counterfactual-Validated → Reproducible → Minimal → Training-Validated`

## The ten-line skeleton

```python
episode, snapshots = collector.run_episode(task, workspace, policy)   # record
iv = Intervention(...)                       # an alternative action, any source
unit = replayer.paired_replay(episode, snapshots, iv)  # control + branch + n× repro
if unit.flipped:
    export(unit)     # -> SFT / DPO / PRM / memory / regression / verl / TRL
```

Six published data-construction strategies are reproduced on this skeleton in
43–78 lines each — including a June-2026 paper reproduced same-day. See
[Case studies](cases.md).

## Headline numbers

| Claim | Result |
|---|---|
| Flip reproducibility (kill line ≥90%) | **100% across 11 configurations** |
| Control-branch digest match | **100%**, with CI-enforced negative controls |
| Mechanism-layer replay savings | **26%** at identical output |
| Selective revalidation (2 real version events) | **4.8× / 8.0×**, zero missed demotions |
| Checkpoint forking vs from-scratch replay | **298×** |

Every number — including the honest nulls — is wired to an experiment and a
pre-registered threshold in the
[claims ledger](https://github.com/JayLZhou/CausalData-Juicer/blob/main/experiments/claims.md).

## Start here

- [Getting started](getting-started.md) — install and run the demo in two minutes
- [Tutorial](tutorial.md) — your first causal unit in ten minutes, plain Python
- [Concepts](concepts.md) — the five objects, the evidence ladder, the four-question fit test
