# 14-day productization plan — executed day by day

Goal: from working demo to a complete product. Each day has deliverables and
an acceptance check. Days needing humans are marked 🧑 (user); everything
else I execute autonomously and check off with the commit hash.

| Day | Deliverables | Acceptance | Status |
|---|---|---|---|
| 1 | Positioning locked: primary scenario = *validated repair data from failed trajectories*; definition-first front page + landscape table + hero figure | reader answers "what do I feed it / what do I get" in 15s | ✅ `15b4e70`…`cc698a9` |
| 2 | Three entry points shipped: `cdj demo` / `cdj import-trace` / `cdj run --repo --verify` | each has a command, output, and next step | ✅ `60883cc` |
| 3 | Zero-config UX: `cdj doctor`, PATH-fallback command resolution, reasoning-model `<think>` handling | clean machine → first causal unit ≤10 min | ✅ `60883cc` |
| 4 | Result page: `cdj explain` cards + static HTML (which step, diff, why causal, tier, cost) | a non-developer understands one unit | ✅ `60883cc` |
| 5 | **Proof-by-replay**: relocatable snapshots (pointer v2 + `cdj migrate-run`), committed replay pack reproducing a live case byte-for-byte offline | anyone re-executes our claims without a model | ✅ `6c6f3de` |
| 6 | The full story doc: one dependency-migration walkthrough with real commands, artifacts, costs (from `runs/depmig-kitchen-sink`) + `cdj verify-claims` scorecard command | every README number has a one-command reproduction entry | ⏳ next |
| 7 | Bring-your-own-task template: copyable minimal workload + verifier + tool example; `cdj run` polish from story-writing friction | new user integrates one task ≤1 h | ⏳ |
| 8 | Docs completeness: FAQ + Troubleshooting pages (seeded from the friction log), integrations page (TRL/verl snippets) | no source-diving needed for next steps | ⏳ |
| 9 | Release engineering: version bump, CHANGELOG 1.0 draft, PyPI packaging dry-run (`python -m build`, twine check), Release notes draft | artifacts build clean locally | ⏳ |
| 10 | 🧑 external testers round 1 (3–5 people, observe silently) — I prepare the observation sheet + tasks | completion rate, friction list, time-to-first-unit recorded | blocked on 🧑 |
| 11 | Fix top-5 frictions from Day 10 | same testers retry measurably faster | blocked on D10 |
| 12 | 🧑 launch materials: 90s video script + shot list (I write), architecture fig ✅, before/after case ✅, FAQ ✅ | page communicates without narration | I prep, 🧑 records |
| 13 | 🧑 soft launch: repo public + Pages on + share to researchers/agent devs | ≥2 external users complete a real task | blocked on 🧑 |
| 14 | 🧑 1.0: GitHub Release + PyPI publish (token) + docs live + roadmap issue + feedback entry | install/demo/docs/downloads all verified online | blocked on 🧑 |

## Launch metrics (unchanged)

80% unaided demo success · first unit <10 min · own-repo <1 h · ≥2 external
users complete a real task · users articulate vs "just ask an LLM" · every
public number has a reproduction entry point.

## Friction log (dogfooding; all fixed)

1. bare `pytest` off PATH → `{python} -m` fallback
2. reasoning-model `<think>` truncation → stripping + repo-context injection
3. agent success produced nothing → success-mining (identity-control re-record)
4. **observed reward hacking** (agent rewrote the test) → SealedVerifier
5. absolute env-pointer paths broke on repo move → pointer v2 + migrate-run
6. rebrand sed renamed on-disk contract filenames → restored; rule recorded:
   data formats are contracts
