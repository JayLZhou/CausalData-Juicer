import click

REGIONS = ['east', 'west', 'north']


def complete_region(ctx, args, incomplete):
    return [r for r in REGIONS if r.startswith(incomplete)]


@click.command()
@click.option('--region', autocompletion=complete_region, default='east')
def deploy(region):
    click.echo(f'deploying to {region}')
