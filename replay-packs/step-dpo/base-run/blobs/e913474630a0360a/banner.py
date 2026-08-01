import click


def banner(text):
    width, _height = click.get_terminal_size()
    width = min(width, 40)
    return text.center(width, '=')
