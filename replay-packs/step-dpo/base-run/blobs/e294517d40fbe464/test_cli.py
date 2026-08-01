from click.testing import CliRunner

from cli import deploy


def test_default_region():
    result = CliRunner().invoke(deploy, [])
    assert result.exit_code == 0
    assert 'deploying to east' in result.output


def test_explicit_region():
    result = CliRunner().invoke(deploy, ['--region', 'west'])
    assert 'deploying to west' in result.output
