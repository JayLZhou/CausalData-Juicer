from click.testing import CliRunner

from app import cli


def test_status():
    result = CliRunner().invoke(cli, ['status', '--env', 'prod'])
    assert result.output.strip() == 'status:prod'


def test_logs_default():
    result = CliRunner().invoke(cli, ['logs'])
    assert result.output.strip() == 'logs:dev'
