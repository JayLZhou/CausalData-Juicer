# D12 — 90-second demo video: script + shot list

Format: screen recording, terminal + one browser tab. No talking head.
Voiceover lines are written to be read at a calm pace; total ≈ 90s.

| # | ⏱ | Screen | Voiceover |
|---|---|---|---|
| 1 | 0–8s | Hero figure (overview.png), slow zoom on the juicer | "Your agents fail all day. The logs tell you what happened — never what would have worked." |
| 2 | 8–18s | Terminal: `cdj run --repo ./my-project --verify "pytest -q"` scrolls: baseline fails, agent attempt, candidates | "Point CausalData-Juicer at a failing repo and any check command." |
| 3 | 18–35s | The explain card appears; highlight lines one by one: Control replay MATCHED → Intervened PASS → Reproduction 3/3 | "Every candidate fix is executed twice: a control branch must reproduce the failure — then the fix must flip it. Three times." |
| 4 | 35–45s | Highlight the diff block, then `Evidence: MINIMAL · Cost: 4 replays / 1.8s` | "You get the minimal change that causally flips the outcome — with its evidence level and its price." |
| 5 | 45–55s | `ls exports/` → open trl-dpo.jsonl, one row visible | "Out come trainer-ready SFT and DPO pairs — TRL and verl formats included." |
| 6 | 55–68s | Split shot: agent editing test file (red) → `SealedVerifier` log line; then `cdj revalidate` demoting units (rollback event) | "It catches agents that cheat by editing tests. And when a dependency moves, it revalidates exactly what that change can touch — and demotes what went stale." |
| 7 | 68–80s | `cdj verify-claims` scorecard scrolling to 8/8 PASS | "Every number we publish re-earns itself on your machine. Including our nulls." |
| 8 | 80–90s | README hero + repo URL + `pip install causal-data-juicer` | "One counterfactual execution machine. Any causal data strategy in about a hundred lines. CausalData-Juicer." |

## Recording checklist

- Terminal 120×32, dark theme, font ≥16pt; `cdj` freshly installed in a
  clean venv (no local artifacts visible).
- Pre-run every command once (warm caches) so takes are smooth; the
  `cdj run` take can be time-lapsed ×4 between candidate lines.
- Scene 6's cheat moment: reuse the real byo-myproj run — the agent
  genuinely did this; screenshot the tampered test line for the red flash.
- Export 1080p, subtitles burned (many watch muted).
