# Bring-your-own-task template

Copy this directory, adapt three things, and `cdj run` does the rest.

1. **Your code** — put the project files here (or point --repo at your repo).
2. **Your check** — anything with an exit code:
   `cdj run --repo . --verify "pytest -q"` or `--verify "make test"` or
   `--verify "{python} check.py"`.
3. **Your endpoint** — any OpenAI-compatible URL via `--base-url/--model`.

Protected files: anything matching `test_*.py`, `*_test.py`, `tests/**`,
`conftest.py` is sealed — restored before every verification, so neither the
agent nor a candidate fix can pass by editing the check itself.

Worked example in this directory: a deliberately broken `pricing.py` whose
tax calculation divides by 10. Run:

    cdj run --repo templates/byo-task --verify "pytest -q" \
        --base-url http://127.0.0.1:8021/v1 --model Qwen/Qwen2.5-7B-Instruct

Expected: baseline fails → agent attempt → candidate fixes → paired-replay
validation → `report.html` with evidence-tiered units and diffs.
