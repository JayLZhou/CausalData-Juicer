"""numpy 1.26 -> 2.0 migration family (6 tasks).

Breaks used (all verified against the built envs by the certificate):
  n01  np.float_ / np.NaN removed                     (AttributeError)
  n02  np.cumproduct removed (-> np.cumprod)          (AttributeError)
       (np.trapz was tried first but still exists in 2.0)
  n03  np.alltrue / np.round_ / np.Inf removed        (multi-point)
  n04  np.array(copy=False) now raises when a copy
       is unavoidable (-> np.asarray)                 (ValueError, 2 sites)
  n05  np.msort / np.product removed                  (multi-point)
  n06  NEP 50: float32 no longer promotes on big
       python scalars -> silent inf                   (T3, silent)
"""
from __future__ import annotations

from causeforge.workloads.depmig.base import DepMigTask, Family

FAMILY = Family(
    name="numpy",
    old_pins=["numpy==1.26.4"],
    new_pins=["numpy==2.0.2"],
)


def build_tasks() -> list[DepMigTask]:
    tasks: list[DepMigTask] = []

    tasks.append(DepMigTask(
        id="n01_scalar_aliases", family=FAMILY, tier=1,
        description="A stats helper using legacy numpy scalar aliases.",
        migration_points=["np.float_ -> np.float64", "np.NaN -> np.nan"],
        files={
            "stats.py": (
                "import numpy as np\n"
                "\n"
                "\n"
                "def to_float_array(values):\n"
                "    return np.array(values, dtype=np.float_)\n"
                "\n"
                "\n"
                "def fill_missing(values):\n"
                "    arr = to_float_array(values)\n"
                "    arr[np.isnan(arr)] = 0.0\n"
                "    return arr.tolist()\n"
                "\n"
                "\n"
                "MISSING = np.NaN\n"
            ),
            "test_stats.py": (
                "import math\n"
                "\n"
                "from stats import MISSING, fill_missing, to_float_array\n"
                "\n"
                "\n"
                "def test_missing_is_nan():\n"
                "    assert math.isnan(MISSING)\n"
                "\n"
                "\n"
                "def test_fill_missing():\n"
                "    assert fill_missing([1.0, MISSING, 3.0]) == [1.0, 0.0, 3.0]\n"
                "\n"
                "\n"
                "def test_dtype():\n"
                "    assert to_float_array([1]).dtype.kind == 'f'\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="n02_cumproduct", family=FAMILY, tier=1,
        description="Compound-growth helper built on np.cumproduct.",
        migration_points=["np.cumproduct -> np.cumprod"],
        files={
            "growth.py": (
                "import numpy as np\n"
                "\n"
                "\n"
                "def compound(factors):\n"
                "    return np.cumproduct(np.array(factors)).tolist()\n"
            ),
            "test_growth.py": (
                "from growth import compound\n"
                "\n"
                "\n"
                "def test_compound():\n"
                "    assert compound([2.0, 3.0, 0.5]) == [2.0, 6.0, 3.0]\n"
                "\n"
                "\n"
                "def test_single():\n"
                "    assert compound([5]) == [5]\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="n03_removed_funcs", family=FAMILY, tier=2,
        description="Validation helpers spread over two modules, using removed numpy functions.",
        migration_points=["np.alltrue -> np.all", "np.round_ -> np.round", "np.Inf -> np.inf"],
        files={
            "checks.py": (
                "import numpy as np\n"
                "\n"
                "\n"
                "def all_positive(values):\n"
                "    return bool(np.alltrue(np.array(values) > 0))\n"
                "\n"
                "\n"
                "UNBOUNDED = np.Inf\n"
            ),
            "rounding.py": (
                "import numpy as np\n"
                "\n"
                "from checks import UNBOUNDED\n"
                "\n"
                "\n"
                "def round2(values):\n"
                "    return np.round_(np.array(values), 2).tolist()\n"
                "\n"
                "\n"
                "def clip_upper(values, bound=UNBOUNDED):\n"
                "    return np.minimum(np.array(values), bound).tolist()\n"
            ),
            "test_checks.py": (
                "from checks import all_positive\n"
                "from rounding import clip_upper, round2\n"
                "\n"
                "\n"
                "def test_all_positive():\n"
                "    assert all_positive([1, 2, 3])\n"
                "    assert not all_positive([1, -2])\n"
                "\n"
                "\n"
                "def test_round2():\n"
                "    assert round2([1.234, 5.678]) == [1.23, 5.68]\n"
                "\n"
                "\n"
                "def test_clip_default_unbounded():\n"
                "    assert clip_upper([1.0, 99.0]) == [1.0, 99.0]\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="n04_copy_false", family=FAMILY, tier=2,
        description="Buffer utilities that pass copy=False where a copy is unavoidable.",
        migration_points=["np.array(list, copy=False) raises in 2.0 -> np.asarray (two sites)"],
        files={
            "buffers.py": (
                "import numpy as np\n"
                "\n"
                "\n"
                "def as_row(values):\n"
                "    return np.array(values, dtype=np.float64, copy=False).reshape(1, -1)\n"
                "\n"
                "\n"
                "def stack_rows(rows):\n"
                "    mats = [np.array(r, dtype=np.float64, copy=False) for r in rows]\n"
                "    return np.vstack(mats)\n"
            ),
            "test_buffers.py": (
                "from buffers import as_row, stack_rows\n"
                "\n"
                "\n"
                "def test_as_row_shape():\n"
                "    assert as_row([1, 2, 3]).shape == (1, 3)\n"
                "\n"
                "\n"
                "def test_stack():\n"
                "    out = stack_rows([[1, 2], [3, 4]])\n"
                "    assert out.shape == (2, 2)\n"
                "    assert out[1, 1] == 4\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="n05_msort_product", family=FAMILY, tier=2,
        description="Ranking helpers using np.msort and np.product.",
        migration_points=["np.msort -> np.sort(axis=0)", "np.product -> np.prod"],
        files={
            "ranking.py": (
                "import numpy as np\n"
                "\n"
                "\n"
                "def sorted_scores(scores):\n"
                "    return np.msort(np.array(scores)).tolist()\n"
                "\n"
                "\n"
                "def combined_odds(factors):\n"
                "    return float(np.product(np.array(factors)))\n"
            ),
            "test_ranking.py": (
                "from ranking import combined_odds, sorted_scores\n"
                "\n"
                "\n"
                "def test_sorted():\n"
                "    assert sorted_scores([3, 1, 2]) == [1, 2, 3]\n"
                "\n"
                "\n"
                "def test_odds():\n"
                "    assert combined_odds([2.0, 0.5, 3.0]) == 3.0\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="n06_nep50_promotion", family=FAMILY, tier=3,
        description="Sensor scaling that silently relied on value-based promotion to float64.",
        migration_points=[
            "NEP 50: float32 * big python scalar stays float32 (inf) in 2.0 — promote explicitly (silent behavioural change)",
        ],
        files={
            "scaling.py": (
                "import numpy as np\n"
                "\n"
                "\n"
                "def scale_readings(readings):\n"
                "    # readings arrive as float32 from the sensor driver\n"
                "    arr = np.array(readings, dtype=np.float32)\n"
                "    return (arr * 1e39).tolist()\n"
            ),
            "test_scaling.py": (
                "import math\n"
                "\n"
                "from scaling import scale_readings\n"
                "\n"
                "\n"
                "def test_values_stay_finite():\n"
                "    out = scale_readings([1.5, 2.0])\n"
                "    assert all(math.isfinite(v) for v in out)\n"
                "    assert out[0] == 1.5e39\n"
            ),
        },
    ))

    return tasks
