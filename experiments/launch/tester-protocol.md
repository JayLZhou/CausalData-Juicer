# D10 — external tester protocol (silent observation)

Goal: watch 3–5 people install, understand, and integrate **without any
help**. You may not answer questions during the run; note them instead.

## Setup (per tester)

- A machine you have NOT prepared beyond: Python 3.11+, git, network.
- Screen share or shoulder-watch. Start a timer at `git clone`.
- Give them ONLY this line: *"It turns agent failures into verified training
  data — try it: github.com/JayLZhou/CausalData-Juicer"*.

## The three tasks (in order, no hints)

1. **Understand & first unit** — expected path: README → `cdj doctor` →
   `cdj demo` → `cdj explain runs/demo`.
   ⏱ record: time to first validated unit; did they find `explain`?
2. **Bring traces** — hand them `sample-traces.jsonl` (5 rows, prepared
   below). Expected: `cdj import-trace`.
   ⏱ record: did they understand the OBSERVED ceiling message?
3. **Bring a repo** — hand them a copy of `templates/byo-task/` and an
   endpoint URL. Expected: `cdj run --repo ... --verify "pytest -q"`.
   ⏱ record: time to report.html; any PATH/endpoint stumbles.

## Record sheet (one per tester)

| Metric | Value |
|---|---|
| T0 → demo completes unaided | ___ min (target ≤10) |
| T0 → own-repo report.html | ___ min (target ≤60) |
| Tasks completed without help | ___ / 3 |
| Questions they asked (verbatim) | |
| Where they got stuck ≥2 min (screen + moment) | |
| Their one-sentence description of the product afterwards | |
| Can they say how it differs from "ask an LLM to fix it"? (verbatim) | |

## Afterwards (10 min interview)

Ask exactly: “What did you expect it to do that it didn't?”, “What would
make you use this on your real project?”, “What's the price of NOT having
the validation step?” — write answers verbatim, no paraphrasing.

## Exit criteria for D10

≥80% task-1 unaided completion; a ranked list of the top friction points
(D11 fixes the top five, then the same testers retry).
