import click


@click.group(chain=True)
def cli():
    pass


@cli.resultcallback()
def aggregate(results):
    click.echo(f'total={sum(results)}')


@cli.command(name='fetch')
def fetch():
    click.echo('fetched')
    return 2


@cli.command(name='parse')
def parse():
    click.echo('parsed')
    return 3
