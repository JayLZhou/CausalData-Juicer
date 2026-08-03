"""The scorecard's honesty contract: NOT_RUN is a third state, never a PASS.

This exists because an earlier version rendered a skipped replay-pack check
as [PASS] and then printed "All claims re-earned" — exactly the kind of
inflated verification this project is supposed to make impossible.
"""
import io
from contextlib import redirect_stdout
from pathlib import Path

from causal_data_juicer.verify_claims import NOT_COVERED, Scorecard


def _run(card, **kw):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = card.summary(**kw)
    return code, buf.getvalue()


def test_not_run_is_not_rendered_as_pass():
    card = Scorecard()
    buf = io.StringIO()
    with redirect_stdout(buf):
        card.row("A1", "real check", True)
        card.skip("B1", "replay pack NOT verified", "bench envs missing")
    out = buf.getvalue()
    assert "[NOT_RUN] B1" in out
    assert "[PASS] B1" not in out


def test_strict_is_the_default_and_fails_on_not_run():
    card = Scorecard()
    with redirect_stdout(io.StringIO()):
        card.row("A1", "real check", True)
        card.skip("B1", "replay pack NOT verified", "bench envs missing")
    code, out = _run(card)  # no args: default must be strict
    assert code == 1
    assert "1 re-earned, 1 not run, 0 failed" in out
    assert "All required claims executed" not in out


def test_lenient_mode_still_discloses_not_run():
    card = Scorecard()
    with redirect_stdout(io.StringIO()):
        card.row("A1", "real check", True)
        card.skip("B1", "replay pack NOT verified", "bench envs missing")
    code, out = _run(card, strict=False)
    assert code == 0
    assert "NOT verified" in out
    assert "not a full reproduction" in out


def test_any_fail_exits_nonzero():
    card = Scorecard()
    with redirect_stdout(io.StringIO()):
        card.row("A1", "real check", False)
    code, out = _run(card)
    assert code == 1
    assert "FAILED to reproduce" in out


def test_full_pass_message_requires_zero_not_run():
    card = Scorecard()
    with redirect_stdout(io.StringIO()):
        card.row("A1", "real check", True)
    code, out = _run(card)
    assert code == 0
    assert "All required claims executed and passed" in out


def test_scorecard_discloses_uncovered_ledger_rows():
    card = Scorecard()
    with redirect_stdout(io.StringIO()):
        card.row("A1", "real check", True)
    _, out = _run(card)
    assert NOT_COVERED in out
    for cid in ("A7", "A8", "A15", "C1", "C2"):
        assert cid in out


def test_claims_yaml_marks_offline_checks_required():
    import yaml
    reg = yaml.safe_load(
        (Path(__file__).parent.parent / "experiments" / "claims.yaml").read_text())
    claims = reg["claims"]
    assert claims["B1"]["required"] is True          # the replay pack is advertised
    assert claims["A15"]["required"] is False        # GPU-hour claims are archived
    for cid, c in claims.items():
        assert c.get("statement") and c.get("reproducer"), cid
