from click.testing import CliRunner

from pipeline import cli


def test_chain_aggregates():
    result = CliRunner().invoke(cli, ['fetch', 'parse'])
    assert result.exit_code == 0
    assert 'total=5' in result.output
