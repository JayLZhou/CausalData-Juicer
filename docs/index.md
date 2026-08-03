---
hide:
  - navigation
  - toc
---

<div class="cdj-landing" markdown>

<section class="s" style="border-top:none; padding-top: 28px;">
<div class="eyebrow">A budgeted interventional data engine</div>
<h1 class="hero-h">Agent failures in.<br>Certified training data <span class="drop">out.</span></h1>
<p class="sub">Logs tell you what happened — never what <b>would have worked</b>.
CausalData-Juicer forks the exact state before a wrong step, tries candidate fixes
<b>for real</b>, proves the control branch still fails and the fix flips the outcome —
repeatedly — then bottles the result with an <b>evidence tier on every row</b>.</p>
<div class="cta-row">
<a class="btn primary" href="getting-started/">Get started — 2 minutes</a>
<a class="btn ghost" href="https://github.com/JayLZhou/CausalData-Juicer">GitHub</a>
<span class="pipline">pip install causal-data-juicer · cdj demo</span>
</div>
<div class="hero-figure"><img src="assets/overview.png" alt="Overview: raw agent trajectories enter the five-stage causal pipeline and exit as causally validated, evidence-metered training samples."></div>
</section>

<section class="s">
<div class="eyebrow">The ledger · every number pre-registered, nulls included</div>
<div class="ledger">
<div><div class="k">Flip reproducibility</div><div class="v">100<em>%</em></div><div class="note">across 13 configurations, kill line ≥ 90%</div></div>
<div><div class="k">Validated units</div><div class="v">102</div><div class="note">from a doubly-certified 52-task bench</div></div>
<div><div class="k">Cost per unit</div><div class="v">≈3<em>s</em></div><div class="note">$0.00 on local endpoints</div></div>
<div><div class="k">Reproductions</div><div class="v">9</div><div class="note">published strategies, ≤110 lines each</div></div>
<div><div class="k">Tests</div><div class="v">63</div><div class="note">incl. CI negative controls</div></div>
</div>
</section>

<section class="s">
<h2>One loop, executed honestly</h2>
<p class="sub" style="margin-bottom:22px">Every causal claim passes the same five stations — and the control gate <i>refuses</i> environments that drift, instead of certifying them.</p>
<div class="loop">
<div class="stage"><div class="op">fork</div><p>restore the snapshot taken before the step in question</p></div>
<div class="stage gate"><div class="op">control</div><p>recorded actions must reproduce the failure, digest-for-digest</p></div>
<div class="stage"><div class="op">do(·)</div><p>apply the intervention; downstream agents can re-react live</p></div>
<div class="stage"><div class="op">Δ outcome</div><p>the verifier decides; flips must reproduce n / n</p></div>
<div class="stage"><div class="op">bottle</div><p>ddmin to the minimal cause, price it, export it</p></div>
</div>
<div class="ladder">
<div class="rung fill"><div class="cell"></div><div class="tag">Observed</div></div>
<div class="rung fill"><div class="cell"></div><div class="tag">Suggested</div></div>
<div class="rung fill"><div class="cell"></div><div class="tag">CF-Validated</div></div>
<div class="rung fill"><div class="cell"></div><div class="tag">Reproducible</div></div>
<div class="rung fill"><div class="cell"></div><div class="tag">Minimal</div></div>
<div class="rung"><div class="cell"></div><div class="tag">Training-Validated</div></div>
</div>
</section>

<section class="s">
<h2>Three doors in</h2>
<div class="terms" style="margin-top:20px">
<div class="term"><div class="lbl">Understand it</div>
<div class="cmd">cdj demo &amp;&amp; cdj explain runs/demo</div>
<div class="out">FLIP REPRO 18/18 · 6 MINIMAL units
<span class="ok">Control replay MATCHED · Reproduction 3/3</span></div></div>
<div class="term"><div class="lbl">Bring your logs</div>
<div class="cmd">cdj import-trace traces.jsonl</div>
<div class="out">3 episodes ingested
<span class="ok">evidence ceiling: OBSERVED — enforced</span></div></div>
<div class="term"><div class="lbl">Bring a repo</div>
<div class="cmd">cdj run --repo . --verify "pytest -q"</div>
<div class="out">2 certified fixes · report.html
<span class="ok">seal intact — test-editing agents caught</span></div></div>
</div>
</section>

<section class="s">
<h2>Nine papers, one skeleton</h2>
<p class="sub" style="margin-bottom:18px">The branch-and-rollout family hand-builds the same loop per paper. Here it is as a library — see the <a href="cases/">showcase</a> for all nine executed reproductions, from MCTS-style step-DPO (76 lines) to a June-2026 paper reproduced same-day (77 lines) to MAS message credit via reactive replay (85 lines).</p>
</section>

<section class="s">
<div class="null-box">
<div class="eyebrow">The honesty policy</div>
<h2 style="margin-top:8px">We publish our nulls.</h2>
<p class="sub" style="margin:8px 0 0">Our training-value pilot tied exactly — twice, at two data scales. It sits in the <a href="https://github.com/JayLZhou/CausalData-Juicer/blob/main/experiments/claims.md">claims ledger</a> beside the wins. Every number on this page re-earns itself on your machine:</p>
<div class="mono-line">$ cdj verify-claims → 8/8 PASS, including a byte-exact offline replay of a live run</div>
</div>
</section>

<section class="s" style="padding-bottom: 20px;">
<b>Learn more:</b> <a href="why-causal-data/">Why causal data</a> · <a href="concepts/">Concepts</a> · <a href="tutorial/">Tutorial</a> · <a href="story-migration/">The full story</a> · <a href="operator-zoo/">Operator Zoo</a> · <a href="integrations/">Integrations</a> · <a href="faq/">FAQ</a>
</section>

</div>
