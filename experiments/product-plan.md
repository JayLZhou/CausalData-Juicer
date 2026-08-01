# Productization plan (14-day frame, tracked)

Source: user's product review, 2026-08-01. Engine work is done; what ships
value is positioning, first-run experience, result display, a real story,
and external validation.

## Three entry points (status)

| Entry | Command | Status |
|---|---|---|
| Understand | `cdj demo` | ✅ shipped (offline, ~20s) |
| Bring your traces | `cdj import-trace traces.jsonl` | ✅ shipped (OBSERVED ceiling) |
| Bring your repo | `cdj run --repo ./proj --verify "pytest -q"` | ✅ shipped this batch — sealed tests, success-mining, HTML report |

## Day-by-day (done / owner)

- [x] D1 positioning: primary scenario = validated repair data from failed
      trajectories (front page rewritten definition-first)
- [x] D2 first screen: input/output/why, landscape table (done earlier)
- [x] D3 three user paths (above)
- [x] D4 zero-config: `cdj doctor` + PATH-fallback command resolution
- [x] D5 result display: `cdj explain` cards + static HTML (which step, what
      changed as a diff, why causal, tier, cost, exports)
- [ ] D6 full migration story with real artifacts (walkthrough doc) — next
- [ ] D7 bring-your-own-task template (workload/verifier/tool skeleton)
- [x] D8 evidence page: `experiments/claims.md` already maps every number
- [x] D9 docs nav: mkdocs site (quick start / concepts / tutorial / cases / API)
- [ ] D10–11 external user tests + top-5 friction fixes — needs humans (user)
- [ ] D12 launch materials: 90s video (user), architecture fig ✅, before/after ✅
- [ ] D13 soft launch — needs repo public (user)
- [ ] D14 1.0: GitHub Release + PyPI (user provides token) + docs live

## Launch metrics (unchanged)

80% unaided demo success · first unit <10 min · own-repo <1 h · ≥2 external
users complete a real task · users can articulate vs "just ask an LLM" ·
every public number has a reproduction entry point.

## Friction log (dogfooding found these; all fixed)

1. bare `pytest` not on PATH in unactivated venvs → auto `{python} -m` fallback
2. reasoning models (`<think>`) truncated before emitting an action → think-block
   stripping + higher token ceiling + repo-context injection
3. agent solved the task → run produced nothing → success-mining (identity
   control re-record certifies the agent's own fix)
4. **agent rewrote the test file to pass** (real reward hacking, observed) →
   SealedVerifier restores protected files before every check; violations counted
