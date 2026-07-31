# Tutorial: your first causal unit in ten minutes

This walks the whole loop **in plain Python** — record an episode, apply a
counterfactual intervention, validate the flip with paired replay, and compile
training data. Everything runs offline (a scripted agent, no LLM needed).

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
```

## 1. A task and a workspace

A *task* is just a directory with a sealed verifier. Here: implement
`double(x)` so the test passes.

```python
from pathlib import Path

ws = Path("tutorial-ws"); ws.mkdir(exist_ok=True)
(ws / "test_solution.py").write_text(
    "from solution import double\n\n"
    "def test_double():\n    assert double(2) == 4\n"
)
```

## 2. Record an episode

The agent below is scripted (deterministic); a live LLM agent
(`causeforge.runtime.llm_policy.LLMPolicy`) records through the exact same
interface. Note the bug: it returns `x + x + x`.

```python
from causeforge.runtime.agent import ScriptedPolicy, ScriptedStep
from causeforge.runtime.collector import Collector
from causeforge.runtime.tools import default_registry
from causeforge.runtime.verifier import PytestVerifier
from causeforge.store.blob import BlobStore
from causeforge.sdk.schemas import ToolCall

blobs = BlobStore(Path("tutorial-blobs"))
collector = Collector(default_registry(), blobs, PytestVerifier())

policy = ScriptedPolicy([
    ScriptedStep(action=ToolCall(tool="write_file", args={
        "path": "solution.py",
        "content": "def double(x):\n    return x + x + x\n"})),
    ScriptedStep(action=ToolCall(tool="run_pytest", args={})),
])
episode, snapshots = collector.run_episode("double", "implement double(x)", ws, policy)
print(episode.outcome.success)   # False — and every step was snapshotted
```

## 3. Intervene and validate with paired replay

A candidate fix is an `Intervention`. `paired_replay` forks the pre-step
snapshot twice: the **control branch** must reproduce the recorded failure
(otherwise the environment drifted and the unit is refused), then the
**intervened branch** runs, then the flip is reproduced n times.

```python
from causeforge.replay.replayer import Replayer
from causeforge.replay.sandbox import LocalSandbox
from causeforge.sdk.schemas import ArgEdit, Intervention, InterventionType

replayer = Replayer(default_registry(), LocalSandbox(blobs, Path("tutorial-scratch")),
                    PytestVerifier())
fix = Intervention(
    type=InterventionType.TOOL_ARGUMENT_EDIT, target_step=0,
    edits=[ArgEdit(arg="content", op="set",
                   value="def double(x):\n    return 2 * x\n")],
)
unit = replayer.paired_replay(episode, snapshots, fix, n_repro=3)
print(unit.flipped, unit.tier.name)   # True REPRODUCIBLE
```

That `CausalUnit` is the atomic product: *this exact change flips this exact
outcome, reproducibly* — with the evidence tier attached.

## 4. Compile training data

```python
from causeforge.compiler.exports import compile_all
paths = compile_all([unit], [episode], Path("tutorial-exports"))
print(open(paths["dpo"]).read())   # prompt / chosen / rejected / evidence_tier
```

`causeforge export --format trl-dpo|trl-sft|verl` produces trainer-native
formats from any run directory.

## 5. Where to go next

- **Candidate sources**: instead of a hand-written fix, plug an LLM fixer,
  temperature resampling, or validation-in-the-loop refinement
  (`causeforge collect-depmig --sources fixer,fixer-tests,resample --refine-rounds 3`).
- **Any executable workload**: swap `PytestVerifier` for
  `CommandVerifier(["make", "test"])` — success is exit code 0.
- **Budgets**: wrap validation in `AcquisitionEngine` with a `Budget` and a
  policy; mechanisms (control memoization, early stopping) are always on.
- **Reproduce a paper**: the six case studies in
  [`examples/`](https://github.com/JayLZhou/CausalData-Juicer/tree/main/examples)
  each fill this same skeleton in under 80 lines.
