"""pandas 1.5 -> 2.2 migration family (6 tasks, stretch goal).

Runs on a python 3.11 base interpreter (pandas 1.5.3 has no cp312
wheels).  numpy is pinned to the SAME version in both envs so the
breaking change is attributable to pandas alone.

Breaks used (probed against both envs):
  d01  DataFrame.append removed            (-> pd.concat)
  d02  Series.iteritems removed            (-> items)
  d03  set_axis(inplace=) + lookup removed (multi-point)
  d04  mean()/sum() on mixed frames raise  (numeric_only semantics)
  d05  append + iteritems across modules   (multi-file)
  d06  to_datetime mixed-format inference removed (T3, semantic)
"""
from __future__ import annotations

from pathlib import Path

from causal_data_juicer.workloads.depmig.base import DepMigTask, Family

PY311 = "/opt/conda/envs/cf-py311/bin/python"

FAMILY = Family(
    name="pandas",
    old_pins=["pandas==1.5.3", "numpy==1.26.4"],
    new_pins=["pandas==2.2.3", "numpy==1.26.4"],
    base_python=PY311,
)


def available() -> bool:
    return Path(PY311).exists()


def build_tasks() -> list[DepMigTask]:
    tasks: list[DepMigTask] = []

    tasks.append(DepMigTask(
        id="d01_append", family=FAMILY, tier=1,
        description="A row logger built on DataFrame.append.",
        migration_points=["DataFrame.append removed (-> pd.concat)"],
        files={
            "rows.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def add_row(df, a, b):\n"
                "    return df.append({'a': a, 'b': b}, ignore_index=True)\n"
                "\n"
                "\n"
                "def empty():\n"
                "    return pd.DataFrame({'a': pd.Series(dtype='int64'),\n"
                "                         'b': pd.Series(dtype='object')})\n"
            ),
            "test_rows.py": (
                "from rows import add_row, empty\n"
                "\n"
                "\n"
                "def test_add_rows():\n"
                "    df = add_row(add_row(empty(), 1, 'x'), 2, 'y')\n"
                "    assert len(df) == 2\n"
                "    assert df['a'].tolist() == [1, 2]\n"
                "    assert df['b'].tolist() == ['x', 'y']\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="d02_iteritems", family=FAMILY, tier=1,
        description="A series walker using Series.iteritems.",
        migration_points=["Series.iteritems removed (-> Series.items)"],
        files={
            "walk.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def pairs(values):\n"
                "    s = pd.Series(values)\n"
                "    return [(int(i), v) for i, v in s.iteritems()]\n"
            ),
            "test_walk.py": (
                "from walk import pairs\n"
                "\n"
                "\n"
                "def test_pairs():\n"
                "    assert pairs(['a', 'b']) == [(0, 'a'), (1, 'b')]\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="d03_axis_lookup", family=FAMILY, tier=2,
        description="Report table utilities using set_axis(inplace=) and DataFrame.lookup.",
        migration_points=["set_axis(inplace=True) removed",
                          "DataFrame.lookup removed (-> numpy indexing / stack)"],
        files={
            "tables.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def rename_rows(df, names):\n"
                "    df = df.copy()\n"
                "    df.set_axis(names, inplace=True)\n"
                "    return df\n"
                "\n"
                "\n"
                "def diagonal(df, rows, cols):\n"
                "    return list(df.lookup(rows, cols))\n"
            ),
            "test_tables.py": (
                "import pandas as pd\n"
                "\n"
                "from tables import diagonal, rename_rows\n"
                "\n"
                "\n"
                "def test_rename_rows():\n"
                "    df = pd.DataFrame({'v': [1, 2]})\n"
                "    out = rename_rows(df, ['r1', 'r2'])\n"
                "    assert list(out.index) == ['r1', 'r2']\n"
                "\n"
                "\n"
                "def test_diagonal():\n"
                "    df = pd.DataFrame({'x': [1, 2], 'y': [3, 4]}, index=['p', 'q'])\n"
                "    assert diagonal(df, ['p', 'q'], ['x', 'y']) == [1, 4]\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="d04_numeric_only", family=FAMILY, tier=2,
        description="Summary stats over mixed-dtype frames relying on silent column dropping.",
        migration_points=["mean()/median() on mixed frames raise in 2.x (numeric_only, two sites)"],
        files={
            "summary.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def frame():\n"
                "    return pd.DataFrame({'score': [1.0, 3.0], 'grade': ['a', 'b']})\n"
                "\n"
                "\n"
                "def mean_scores(df):\n"
                "    return dict(df.mean())\n"
                "\n"
                "\n"
                "def median_scores(df):\n"
                "    return dict(df.median())\n"
            ),
            "test_summary.py": (
                "from summary import frame, mean_scores, median_scores\n"
                "\n"
                "\n"
                "def test_mean():\n"
                "    assert mean_scores(frame()) == {'score': 2.0}\n"
                "\n"
                "\n"
                "def test_median():\n"
                "    assert median_scores(frame()) == {'score': 2.0}\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="d05_etl_combo", family=FAMILY, tier=2,
        description="A two-module ETL combining append-in-loop and iteritems.",
        migration_points=["DataFrame.append removed", "Series.iteritems removed (second module)"],
        files={
            "collect.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def gather(records):\n"
                "    df = pd.DataFrame({'k': pd.Series(dtype='object'),\n"
                "                       'v': pd.Series(dtype='int64')})\n"
                "    for rec in records:\n"
                "        df = df.append(rec, ignore_index=True)\n"
                "    return df\n"
            ),
            "report.py": (
                "from collect import gather\n"
                "\n"
                "\n"
                "def as_lines(records):\n"
                "    df = gather(records)\n"
                "    return [f'{k}={v}' for _, (k, v) in enumerate(\n"
                "        (row['k'], row['v']) for _, row in df.iterrows())]\n"
                "\n"
                "\n"
                "def value_index_pairs(records):\n"
                "    df = gather(records)\n"
                "    return [(int(i), v) for i, v in df['v'].iteritems()]\n"
            ),
            "test_report.py": (
                "from report import as_lines, value_index_pairs\n"
                "\n"
                "RECORDS = [{'k': 'x', 'v': 1}, {'k': 'y', 'v': 2}]\n"
                "\n"
                "\n"
                "def test_lines():\n"
                "    assert as_lines(RECORDS) == ['x=1', 'y=2']\n"
                "\n"
                "\n"
                "def test_pairs():\n"
                "    assert value_index_pairs(RECORDS) == [(0, 1), (1, 2)]\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="d06_to_datetime", family=FAMILY, tier=3,
        description="An ingest step relying on 1.x per-element datetime format inference.",
        migration_points=[
            "to_datetime no longer infers formats per element in 2.x — the mixed-format "
            "column raises; restore 1.x semantics explicitly (semantic change)",
        ],
        files={
            "ingest.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def parse_dates(raw):\n"
                "    return [d.date().isoformat() for d in pd.to_datetime(raw)]\n"
            ),
            "test_ingest.py": (
                "from ingest import parse_dates\n"
                "\n"
                "\n"
                "def test_mixed_formats_keep_legacy_semantics():\n"
                "    # 1.x parsed each element independently: month-first when\n"
                "    # possible, day-first as fallback\n"
                "    out = parse_dates(['01-02-2000', '13-01-2000'])\n"
                "    assert out == ['2000-01-02', '2000-01-13']\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="d07_series_append", family=FAMILY, tier=1,
        description="A metric accumulator built on Series.append.",
        migration_points=["Series.append removed (-> pd.concat)"],
        files={
            "acc.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def accumulate(chunks):\n"
                "    total = pd.Series(dtype='int64')\n"
                "    for chunk in chunks:\n"
                "        total = total.append(pd.Series(chunk), ignore_index=True)\n"
                "    return total.tolist()\n"
            ),
            "test_acc.py": (
                "from acc import accumulate\n"
                "\n"
                "\n"
                "def test_accumulate():\n"
                "    assert accumulate([[1, 2], [3]]) == [1, 2, 3]\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="d08_mad", family=FAMILY, tier=1,
        description="A dispersion report using DataFrame.mad.",
        migration_points=["DataFrame.mad removed (compose from mean of abs deviations)"],
        files={
            "spread.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def mad_by_column(data):\n"
                "    df = pd.DataFrame(data)\n"
                "    return dict(df.mad())\n"
            ),
            "test_spread.py": (
                "from spread import mad_by_column\n"
                "\n"
                "\n"
                "def test_mad():\n"
                "    assert mad_by_column({'x': [1.0, 3.0]}) == {'x': 1.0}\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="d09_csv_squeeze", family=FAMILY, tier=2,
        description="A CSV loader relying on read_csv(squeeze=) and DataFrame.iteritems.",
        migration_points=["read_csv(squeeze=) removed (-> .squeeze('columns'))",
                          "DataFrame.iteritems removed (-> items)"],
        files={
            "loader.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def load_column(path):\n"
                "    return pd.read_csv(path, squeeze=True).tolist()\n"
                "\n"
                "\n"
                "def column_names(path):\n"
                "    return [name for name, _ in pd.read_csv(path).iteritems()]\n"
            ),
            "test_loader.py": (
                "from loader import column_names, load_column\n"
                "\n"
                "\n"
                "def test_single_column(tmp_path):\n"
                "    p = tmp_path / 'one.csv'\n"
                "    p.write_text('v\\n1\\n2\\n')\n"
                "    assert load_column(p) == [1, 2]\n"
                "\n"
                "\n"
                "def test_names(tmp_path):\n"
                "    p = tmp_path / 'two.csv'\n"
                "    p.write_text('a,b\\n1,2\\n')\n"
                "    assert column_names(p) == ['a', 'b']\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="d10_pivot_combo", family=FAMILY, tier=2,
        description="A two-module report combining df.iteritems and Series.append.",
        migration_points=["DataFrame.iteritems removed", "Series.append removed (second module)"],
        files={
            "shape.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def widths(data):\n"
                "    df = pd.DataFrame(data)\n"
                "    return {name: len(col) for name, col in df.iteritems()}\n"
            ),
            "merge.py": (
                "import pandas as pd\n"
                "\n"
                "\n"
                "def concat_series(a, b):\n"
                "    return pd.Series(a).append(pd.Series(b), ignore_index=True).tolist()\n"
            ),
            "test_combo.py": (
                "from merge import concat_series\n"
                "from shape import widths\n"
                "\n"
                "\n"
                "def test_widths():\n"
                "    assert widths({'a': [1, 2], 'b': [3, 4]}) == {'a': 2, 'b': 2}\n"
                "\n"
                "\n"
                "def test_concat():\n"
                "    assert concat_series([1], [2, 3]) == [1, 2, 3]\n"
            ),
        },
    ))

    return tasks
