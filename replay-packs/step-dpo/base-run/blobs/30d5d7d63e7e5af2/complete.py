ENVS = ['dev', 'staging', 'prod']


def complete_env(ctx, args, incomplete):
    return [e for e in ENVS if e.startswith(incomplete)]
