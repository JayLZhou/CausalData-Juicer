import click


def current_args(argv=None):
    if argv is not None:
        return list(argv)
    return click.get_os_args()


def usage_line(prog):
    width, _ = click.get_terminal_size()
    return f'usage: {prog}'[: max(10, min(width, 60))]
