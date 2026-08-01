# The full story: one failing migration → certified training data

Every number and artifact on this page comes from a real run
(`runs/depmig-kitchen-sink`, archived report in
[`experiments/results/depmig-kitchen-sink.json`](https://github.com/JayLZhou/CausalData-Juicer/blob/main/experiments/results/depmig-kitchen-sink.json)).
Reproduce the offline parts with `cdj verify-claims`; reproduce this exact
pipeline against your own endpoint with the commands shown.

## The task

`p02_str_coercion`, from the certified migration bench: a ticket registry
written for pydantic 1.x, where `Ticket(ticket_id=seq_no, ...)` relied on v1
silently coercing `int → str`. The environment has **pydantic 2.7.4**
installed; v2 refuses the coercion; the sealed tests fail.

## Step 1 — a real agent fails

```bash
cdj collect-depmig --base-url http://127.0.0.1:8021/v1 \
    --model Qwen/Qwen2.5-7B-Instruct --tasks p02_str_coercion
```

The 7B agent reads the failure, edits `tickets.py`, re-runs pytest, and still
fails (its attempts kept `ticket_id: int` or forgot the call site). Snapshots
were taken before every step — the failure is now *forkable*.

## Step 2 — candidate fixes from cheap, diverse sources

```bash
cdj collect-depmig ... --sources fixer-tests,resample --refine-rounds 3 \
    --fixer-model Qwen/Qwen2.5-32B-Instruct-AWQ --fixer-base-url http://127.0.0.1:8020/v1
```

The screener pooled candidates for this failure from a test-aware fixer and
temperature resampling (this family's science: diversity beats strength on
easy/medium tasks, strength wins the hard tail, pooling wins everywhere).

## Step 3 — paired counterfactual validation

For the winning candidate (source: `fixer-tests`):

```text
Task              : p02_str_coercion — A ticket registry that relied on pydantic v1 coercing int ids to str.
Original outcome  : FAIL (0 passed, 2 failed)
Intervention      : ACTION_REPLACE @ step 1 on tickets.py  (source: fixer-tests)
Control replay    : MATCHED
Intervened outcome: PASS
Reproduction      : 3/3
Minimal edit      : 1 atom(s)
Evidence          : MINIMAL
Cost              : 5 replays / 3.1s / $0.0000
What changed      :
    --- agent wrote                     +++ validated fix
     class Ticket(BaseModel):            class Ticket(BaseModel):
    -    ticket_id: int                 +    ticket_id: str
    -    return Ticket(ticket_id=seq_no +    return Ticket(ticket_id=str(seq_no)
```

(That card is `cdj explain runs/depmig-kitchen-sink` output, verbatim.) The
control branch first re-ran the *original* actions and matched the recording
digest-for-digest — only then was the intervened branch credited, and the
flip reproduced from three independent forks.

## Step 4 — training-ready exports

One real row of `exports/dpo.jsonl` (TRL-compatible via `cdj export`):

```json
{"prompt": "Task: ... implement the ticket registry ...",
 "chosen":   "{\"tool\": \"write_file\", ... \"ticket_id: str\" ... str(seq_no) ...}",
 "rejected": "{\"tool\": \"write_file\", ... \"ticket_id: int\" ... seq_no ...}",
 "evidence_tier": "MINIMAL"}
```

Plus `sft.jsonl`, `memory.jsonl` (failure→recovery for agent memory), and an
**executable** `regression.jsonl` + generated pytest suite: on your next
model or dependency upgrade, `cdj regress` re-forks this exact snapshot and
checks the flip still holds.

## Step 5 — when pydantic moves again

```bash
cdj revalidate --family pydantic --pin "pydantic==2.11.7"
```

On the real 2.7.4 → 2.11.7 upgrade event, selective revalidation re-checked
only pydantic-claimed units (5 replays instead of 24), confirmed this fix
survives, and re-stamped its provenance. On a click *rollback* event, the
same machinery correctly *demoted* four units whose original bugs had
vanished — data that silently went stale in a way only a re-run control
branch can see.

## Why this beats "just ask an LLM to fix it"

The 32B fixer also proposed `from pydantic_settings import ...` fixes that
*look* right and crash at import — plausible text, wrong world. Every row
above survived a controlled experiment instead: control matched, outcome
flipped, three reproductions, minimal edit isolated, cost accounted,
validity conditions recorded. That is the difference between **data that
looks correct and data that is certified to change the outcome.**
