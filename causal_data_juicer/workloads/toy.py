"""Toy workload for the M1 end-to-end loop.

Nine tiny "implement the function" tasks driven by a deterministic
scripted mock-LLM agent.  Six episodes fail; the workload ships a fix
table (standing in for a cached fixer-LLM) with candidate interventions:

- t02, t08: ACTION_REPLACE with corrected file content
- t04:      TOOL_ARGUMENT_EDIT set(content)
- t05:      TOOL_ARGUMENT_EDIT set(path)         (content was fine)
- t06:      TOOL_ARGUMENT_EDIT patch_lines with one causal + one cosmetic
            atom — causal slicing must drop the cosmetic one
- t09:      two candidates: a cosmetic non-fix (must fail validation) and
            a real fix (must flip)

t08 also calls the EXTERNAL_SIDE_EFFECT tool ``send_report``, exercising
the dry-run gating during replay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from causal_data_juicer.runtime.agent import ScriptedStep
from causal_data_juicer.sdk.schemas import (
    ArgEdit,
    Intervention,
    InterventionType,
    LinePatch,
    ToolCall,
    digest_of,
)

WORKLOAD_ID = "toy-pyfix-v1"


@dataclass
class ToyTask:
    id: str
    description: str
    files: dict[str, str]  # initial workspace files
    script: list[ScriptedStep]  # deterministic agent actions
    fixes: list[Intervention] = field(default_factory=list)

    def setup(self, workspace: Path) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        for rel, content in self.files.items():
            p = workspace / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)


def _write(path: str, content: str, thought: str = "") -> ScriptedStep:
    return ScriptedStep(
        action=ToolCall(tool="write_file", args={"path": path, "content": content}),
        thought=thought or f"I'll implement {path}.",
    )


def _pytest() -> ScriptedStep:
    return ScriptedStep(action=ToolCall(tool="run_pytest", args={}), thought="Run the tests.")


# ---------------------------------------------------------------------------
# solutions (correct and buggy variants)
# ---------------------------------------------------------------------------

ADD_OK = "def add(a, b):\n    return a + b\n"

FIB_BAD = (
    "def fib(n):\n"
    "    a, b = 0, 1\n"
    "    for _ in range(n):\n"
    "        a, b = b, a + b\n"
    "    return b\n"  # off-by-one: returns fib(n+1)
)
FIB_OK = FIB_BAD.replace("    return b\n", "    return a\n")

SORT_OK = "def sort_desc(xs):\n    return sorted(xs, reverse=True)\n"

REV_BAD = "def reverse_words(s):\n    return s[::-1]\n"
REV_OK = 'def reverse_words(s):\n    return " ".join(s.split()[::-1])\n'

ADD3_OK = "def add3(a, b, c):\n    return a + b + c\n"

PRIME_BAD = (
    "# prime checker utility\n"
    "def is_prime(n):\n"
    "    if n < 2:\n"
    "        return False\n"
    "    for d in range(2, n // 2):\n"  # misses n=4 (empty range)
    "        if n % d == 0:\n"
    "            return False\n"
    "    return True\n"
)
PRIME_CAUSAL_PATCH = LinePatch(line=4, text="    for d in range(2, int(n ** 0.5) + 1):")
PRIME_COSMETIC_PATCH = LinePatch(line=0, text="# prime checker utility (reviewed)")

MEDIAN_OK = (
    "def median(xs):\n"
    "    s = sorted(xs)\n"
    "    n = len(s)\n"
    "    mid = n // 2\n"
    "    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2\n"
)

MEAN_BAD = "def mean(xs):\n    return sum(xs) / (len(xs) + 1)\n"
MEAN_OK = "def mean(xs):\n    return sum(xs) / len(xs)\n"

ABS_BAD = (
    "def abs_val(x):\n"
    "    if x < 0:\n"
    "        return -x\n"
    "    return -x\n"  # always negates
)
ABS_GOOD_PATCH = LinePatch(line=3, text="    return x")
ABS_COSMETIC_PATCH = LinePatch(line=2, text="        return -x  # handles negatives")


def _tests(body: str) -> str:
    return body


# ---------------------------------------------------------------------------
# task definitions
# ---------------------------------------------------------------------------


def build_tasks() -> list[ToyTask]:
    tasks: list[ToyTask] = []

    tasks.append(
        ToyTask(
            id="t01_add",
            description="Implement add(a, b) in solution.py so the tests pass.",
            files={
                "test_solution.py": _tests(
                    "from solution import add\n\n"
                    "def test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n"
                )
            },
            script=[_write("solution.py", ADD_OK), _pytest()],
        )
    )

    tasks.append(
        ToyTask(
            id="t02_fib",
            description="Implement fib(n) (0-indexed Fibonacci) in solution.py.",
            files={
                "test_solution.py": _tests(
                    "from solution import fib\n\n"
                    "def test_fib():\n    assert fib(0) == 0\n    assert fib(1) == 1\n    assert fib(10) == 55\n"
                )
            },
            script=[_write("solution.py", FIB_BAD), _pytest()],
            fixes=[
                Intervention(
                    type=InterventionType.ACTION_REPLACE,
                    target_step=0,
                    new_action=ToolCall(
                        tool="write_file", args={"path": "solution.py", "content": FIB_OK}
                    ),
                    rationale="Loop updates one step too far; return a, not b.",
                )
            ],
        )
    )

    tasks.append(
        ToyTask(
            id="t03_sort",
            description="Implement sort_desc(xs) in solution.py.",
            files={
                "test_solution.py": _tests(
                    "from solution import sort_desc\n\n"
                    "def test_sort():\n    assert sort_desc([1, 3, 2]) == [3, 2, 1]\n"
                )
            },
            script=[_write("solution.py", SORT_OK), _pytest()],
        )
    )

    tasks.append(
        ToyTask(
            id="t04_reverse_words",
            description="Implement reverse_words(s) reversing word order in solution.py.",
            files={
                "test_solution.py": _tests(
                    "from solution import reverse_words\n\n"
                    "def test_rev():\n    assert reverse_words('hello brave world') == 'world brave hello'\n"
                )
            },
            script=[_write("solution.py", REV_BAD), _pytest()],
            fixes=[
                Intervention(
                    type=InterventionType.TOOL_ARGUMENT_EDIT,
                    target_step=0,
                    edits=[ArgEdit(arg="content", op="set", value=REV_OK)],
                    rationale="Reverse words, not characters: split then join reversed.",
                )
            ],
        )
    )

    tasks.append(
        ToyTask(
            id="t05_wrong_path",
            description="Implement add3(a, b, c) in solution.py.",
            files={
                "test_solution.py": _tests(
                    "from solution import add3\n\ndef test_add3():\n    assert add3(1, 2, 3) == 6\n"
                )
            },
            # content is correct but written to the wrong file
            script=[_write("main.py", ADD3_OK), _pytest()],
            fixes=[
                Intervention(
                    type=InterventionType.TOOL_ARGUMENT_EDIT,
                    target_step=0,
                    edits=[ArgEdit(arg="path", op="set", value="solution.py")],
                    rationale="Tests import `solution`; the file went to main.py.",
                )
            ],
        )
    )

    tasks.append(
        ToyTask(
            id="t06_prime",
            description="Implement is_prime(n) in solution.py.",
            files={
                "test_solution.py": _tests(
                    "from solution import is_prime\n\n"
                    "def test_prime():\n"
                    "    assert is_prime(2) and is_prime(13)\n"
                    "    assert not is_prime(1) and not is_prime(4) and not is_prime(9)\n"
                )
            },
            script=[_write("solution.py", PRIME_BAD), _pytest()],
            fixes=[
                Intervention(
                    type=InterventionType.TOOL_ARGUMENT_EDIT,
                    target_step=0,
                    edits=[
                        ArgEdit(
                            arg="content",
                            op="patch_lines",
                            patches=[PRIME_COSMETIC_PATCH, PRIME_CAUSAL_PATCH],
                        )
                    ],
                    rationale="Divisor range must reach sqrt(n); comment touch-up is incidental.",
                )
            ],
        )
    )

    tasks.append(
        ToyTask(
            id="t07_median",
            description="Implement median(xs) in solution.py.",
            files={
                "test_solution.py": _tests(
                    "from solution import median\n\n"
                    "def test_median():\n    assert median([3, 1, 2]) == 2\n    assert median([1, 2, 3, 4]) == 2.5\n"
                )
            },
            script=[_write("solution.py", MEDIAN_OK), _pytest()],
        )
    )

    tasks.append(
        ToyTask(
            id="t08_report",
            description="Implement mean(xs) in solution.py, then send a status report.",
            files={
                "test_solution.py": _tests(
                    "from solution import mean\n\n"
                    "def test_mean():\n    assert mean([1, 2, 3]) == 2\n"
                )
            },
            script=[
                _write("solution.py", MEAN_BAD),
                _pytest(),
                ScriptedStep(
                    action=ToolCall(tool="send_report", args={"message": "task t08 finished"}),
                    thought="Notify the channel.",
                ),
            ],
            fixes=[
                Intervention(
                    type=InterventionType.ACTION_REPLACE,
                    target_step=0,
                    new_action=ToolCall(
                        tool="write_file", args={"path": "solution.py", "content": MEAN_OK}
                    ),
                    rationale="Mean divides by len(xs), not len(xs)+1.",
                )
            ],
        )
    )

    tasks.append(
        ToyTask(
            id="t09_abs",
            description="Implement abs_val(x) in solution.py.",
            files={
                "test_solution.py": _tests(
                    "from solution import abs_val\n\n"
                    "def test_abs():\n    assert abs_val(-3) == 3\n    assert abs_val(3) == 3\n"
                )
            },
            script=[_write("solution.py", ABS_BAD), _pytest()],
            fixes=[
                # plausible-but-wrong candidate: cosmetic comment, no behaviour change
                Intervention(
                    type=InterventionType.TOOL_ARGUMENT_EDIT,
                    target_step=0,
                    edits=[ArgEdit(arg="content", op="patch_lines", patches=[ABS_COSMETIC_PATCH])],
                    rationale="Annotate the negative branch (non-fix control).",
                ),
                # real fix
                Intervention(
                    type=InterventionType.TOOL_ARGUMENT_EDIT,
                    target_step=0,
                    edits=[ArgEdit(arg="content", op="patch_lines", patches=[ABS_GOOD_PATCH])],
                    rationale="Positive branch must return x unchanged.",
                ),
            ],
        )
    )

    return tasks


def fix_table(tasks: list[ToyTask]) -> dict[str, list[Intervention]]:
    return {t.id: t.fixes for t in tasks if t.fixes}


def workload_digest(tasks: list[ToyTask]) -> str:
    return digest_of(
        [
            {
                "id": t.id,
                "files": t.files,
                "script": [s.action.model_dump() for s in t.script],
                "fixes": [f.effect_signature() for f in t.fixes],
            }
            for t in tasks
        ]
    )
