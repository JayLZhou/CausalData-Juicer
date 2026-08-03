"""The scorecard's honesty contract: SKIP is a third state, never a PASS.

This exists because an earlier version rendered a skipped replay-pack check
as [PASS] and then printed "All claims re-earned" — exactly the kind of
inflated verification this project is supposed to make impossible.
"""
import io
from contextlib import redirect_stdout

from causal_data_juicer.verify_claims import NOT_COVERED, Scorecard


def _run(card, strict=False):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = card.summary(strict)
    return code, buf.getvalue()


def test_skip_is_not_rendered_as_pass():
    card = Scorecard()
    buf = io.StringIO()
    with redirect_stdout(buf):
        card.row("A1", "real check", True)
        card.skip("B1", "replay pack NOT verified", "bench envs missing")
    out = buf.getvalue()
    assert "[SKIP] B1" in out
    assert "[PASS] B1" not in out


def test_summary_with_skips_never_claims_everything_verified():
    card = Scorecard()
    with redirect_stdout(io.StringIO()):
        card.row("A1", "real check", True)
        card.skip("B1", "replay pack NOT verified", "bench envs missing")
    code, out = _run(card)
    assert code == 0  # non-strict: skips do not fail the run...
    assert "1 re-earned, 1 skipped, 0 failed" in out
    assert "NOT verified" in out            # ...but are loudly reported
    assert "Every offline-verifiable check passed" not in out


def test_strict_turns_skips_into_failures():
    card = Scorecard()
    with redirect_stdout(io.StringIO()):
        card.skip("B1", "replay pack NOT verified", "bench envs missing")
    code, _ = _run(card, strict=True)
    assert code == 1


def test_any_fail_exits_nonzero():
    card = Scorecard()
    with redirect_stdout(io.StringIO()):
        card.row("A1", "real check", False)
    code, out = _run(card)
    assert code == 1
    assert "FAILED to reproduce" in out


def test_scorecard_discloses_uncovered_ledger_rows():
    card = Scorecard()
    with redirect_stdout(io.StringIO()):
        card.row("A1", "real check", True)
    _, out = _run(card)
    assert NOT_COVERED in out
    for cid in ("A7", "A8", "A15", "C1", "C2"):
        assert cid in out
