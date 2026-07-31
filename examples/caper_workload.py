"""Mini Text-to-SQL workload for the CAPER case study (arXiv:2606.03327).

SQL is written one clause per line on a fixed scaffold
(SELECT / FROM / WHERE / GROUP BY / HAVING / ORDER BY), so a clause is
exactly a LinePatch atom.  Sealed tests execute solution.sql against an
in-memory sqlite seeded inline and compare to gold rows — hermetic and
deterministic.
"""
from __future__ import annotations


def sql_test(seed: str, gold: str) -> str:
    return (
        "import pathlib\n"
        "import sqlite3\n"
        "\n"
        f"SEED = '''{seed}'''\n"
        f"GOLD = {gold}\n"
        "\n"
        "\n"
        "def test_query():\n"
        "    con = sqlite3.connect(':memory:')\n"
        "    con.executescript(SEED)\n"
        "    sql = pathlib.Path('solution.sql').read_text()\n"
        "    assert con.execute(sql).fetchall() == GOLD\n"
    )


EMP_SEED = (
    "CREATE TABLE employees (name TEXT, dept TEXT, salary REAL);"
    "INSERT INTO employees VALUES"
    "('alice','IT',90),('bob','IT',70),('carol','HR',50),('dan','HR',80),('eve','ML',100);"
)

# repair-direction task: the agent used WHERE where HAVING belongs
REPAIR = {
    "id": "sql_avg_salary",
    "question": "Departments whose average salary exceeds 70, with the average, ordered by dept.",
    "test": sql_test(EMP_SEED, "[('IT', 80.0), ('ML', 100.0)]"),
    "wrong_sql": [
        "SELECT dept, AVG(salary)",
        "FROM employees",
        "WHERE salary > 70",
        "GROUP BY dept",
        "HAVING 1=1",
        "ORDER BY dept",
    ],
    # candidate clause edits (line -> replacement); the full fix needs BOTH
    "clause_fixes": {2: "WHERE 1=1", 4: "HAVING AVG(salary) > 70"},
}

PROD_SEED = (
    "CREATE TABLE products (name TEXT, cat TEXT, price REAL);"
    "INSERT INTO products VALUES"
    "('kbd','hw',30),('gpu','hw',900),('ide','sw',0),('db','sw',120),('mouse','hw',20);"
)

# stress-direction task: the query is CORRECT; perturb each clause and
# observe which perturbations break execution equivalence
STRESS = {
    "id": "sql_expensive_hw",
    "question": "Names of hardware products over 25, ordered by name.",
    "test": sql_test(PROD_SEED, "[('gpu',), ('kbd',)]"),
    "correct_sql": [
        "SELECT name",
        "FROM products",
        "WHERE cat = 'hw' AND price > 25",
        "GROUP BY name",
        "HAVING 1=1",
        "ORDER BY name",
    ],
    "perturbations": {
        0: ["SELECT name, price"],                  # breaks shape        -> critical
        2: ["WHERE cat = 'hw'",                     # drops price filter  -> critical
            "WHERE price > 25 AND cat = 'hw'"],     # commuted            -> harmless
        4: ["HAVING COUNT(*) >= 1"],                # vacuous             -> harmless
        5: ["ORDER BY name ASC",                    # explicit default    -> harmless
            "ORDER BY name DESC"],                  # flips order         -> critical
    },
}
