from click.testing import CliRunner

from serve import serve


def test_runs_quiet_by_default():
    result = CliRunner().invoke(serve, [])
    assert result.output.strip() == 'verbose=False'


def test_help_documents_default_contract():
    result = CliRunner().invoke(serve, ['--help'])
    assert result.exit_code == 0
    assert '[default: False]' in result.output
