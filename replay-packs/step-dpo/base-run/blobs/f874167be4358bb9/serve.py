import click


@click.command()
@click.option('--verbose/--quiet', default=False, help='log every request',
              show_default=True)
def serve(verbose):
    click.echo(f'verbose={verbose}')
