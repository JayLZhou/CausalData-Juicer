import click


def banner(text):
    width, _ = click.get_terminal_size()
    width = min(width, 40)
    return text.center(width, '=')

if __name__ == '__main__':
    import sys
    print(banner(sys.argv[1]))