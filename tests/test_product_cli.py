"""Product-surface tests: doctor, explain (text + HTML), command resolution."""
import sys

from causal_data_juicer.pipeline import run_demo
from causal_data_juicer.report import explain_html, explain_text
from causal_data_juicer.runtime.verifier import resolve_command


def test_resolve_command_falls_back_to_python_module(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    argv = resolve_command(["pytest", "-q"], tmp_path)
    assert argv[0] == sys.executable and argv[1:3] == ["-m", "pytest"]
    # absolute paths and {python} pass through untouched
    assert resolve_command(["{python}", "x.py"], tmp_path)[0] == sys.executable
    assert resolve_command(["/bin/echo", "hi"], tmp_path) == ["/bin/echo", "hi"]


def test_explain_text_and_html(tmp_path):
    run_dir = tmp_path / "run"
    run_demo(run_dir, n_repro=2)

    text = explain_text(run_dir)
    assert "Control replay    : MATCHED" in text
    assert "Reproduction      : 2/2" in text
    assert "Evidence          : MINIMAL" in text
    assert "What changed      :" in text and "+++ validated fix" in text

    html_path = explain_html(run_dir, tmp_path / "report.html")
    html = html_path.read_text()
    assert html.count('class="card"') == 6  # six validated toy units
    assert "MINIMAL" in html and "Reproduction" in html


def test_doctor_runs_clean(capsys):
    from causal_data_juicer.doctor import run_doctor
    code = run_doctor(base_url=None)
    out = capsys.readouterr().out
    assert code == 0
    assert "python" in out and "scratch space writable" in out
