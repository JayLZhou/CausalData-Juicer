import click

from complete import complete_env


@click.group()
def cli():
    pass

@cli.command(name='status')
@click.option('--env', autocompletion=complete_env, default='dev')
def status(env):
    click.echo(f'status:{env}')

@cli.command(name='logs')
@click.option('--env', autocompletion=complete_env, default='dev')
def logs(env):
    click.echo(f'logs:{env}')
