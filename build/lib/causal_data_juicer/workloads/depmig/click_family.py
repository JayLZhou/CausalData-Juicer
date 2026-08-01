"""click 7 -> 8 migration family (6 tasks).

Breaks used:
  c01  click.get_terminal_size removed
  c02  autocompletion= parameter removed (-> shell_complete)
  c03  click.get_os_args removed + get_terminal_size (multi-point)
  c04  Group.resultcallback removed in 8.1 (-> result_callback)
  c05  autocompletion on two options across two modules (multi-file)
  c06  boolean-flag help shows [default: quiet] not [default: False]
       (T3: silent output change; probed against both envs)
"""
from __future__ import annotations

from causal_data_juicer.workloads.depmig.base import DepMigTask, Family

FAMILY = Family(
    name="click",
    old_pins=["click==7.1.2"],
    new_pins=["click==8.1.7"],
)


def build_tasks() -> list[DepMigTask]:
    tasks: list[DepMigTask] = []

    tasks.append(DepMigTask(
        id="c01_terminal_size", family=FAMILY, tier=1,
        description="A banner printer using click.get_terminal_size.",
        migration_points=["click.get_terminal_size removed (-> shutil.get_terminal_size)"],
        files={
            "banner.py": (
                "import click\n"
                "\n"
                "\n"
                "def banner(text):\n"
                "    width, _height = click.get_terminal_size()\n"
                "    width = min(width, 40)\n"
                "    return text.center(width, '=')\n"
            ),
            "test_banner.py": (
                "from banner import banner\n"
                "\n"
                "\n"
                "def test_banner_centered():\n"
                "    out = banner('hi')\n"
                "    assert 'hi' in out\n"
                "    assert out.startswith('=') and out.endswith('=')\n"
                "    assert len(out) <= 40\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="c02_autocompletion", family=FAMILY, tier=1,
        description="A CLI option using the autocompletion= parameter.",
        migration_points=["autocompletion= removed (-> shell_complete=)"],
        files={
            "cli.py": (
                "import click\n"
                "\n"
                "REGIONS = ['east', 'west', 'north']\n"
                "\n"
                "\n"
                "def complete_region(ctx, args, incomplete):\n"
                "    return [r for r in REGIONS if r.startswith(incomplete)]\n"
                "\n"
                "\n"
                "@click.command()\n"
                "@click.option('--region', autocompletion=complete_region, default='east')\n"
                "def deploy(region):\n"
                "    click.echo(f'deploying to {region}')\n"
            ),
            "test_cli.py": (
                "from click.testing import CliRunner\n"
                "\n"
                "from cli import deploy\n"
                "\n"
                "\n"
                "def test_default_region():\n"
                "    result = CliRunner().invoke(deploy, [])\n"
                "    assert result.exit_code == 0\n"
                "    assert 'deploying to east' in result.output\n"
                "\n"
                "\n"
                "def test_explicit_region():\n"
                "    result = CliRunner().invoke(deploy, ['--region', 'west'])\n"
                "    assert 'deploying to west' in result.output\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="c03_os_args", family=FAMILY, tier=2,
        description="A dispatcher built on click.get_os_args plus terminal sizing.",
        migration_points=["click.get_os_args removed (-> sys.argv[1:])",
                          "click.get_terminal_size removed"],
        files={
            "dispatch.py": (
                "import click\n"
                "\n"
                "\n"
                "def current_args(argv=None):\n"
                "    if argv is not None:\n"
                "        return list(argv)\n"
                "    return click.get_os_args()\n"
                "\n"
                "\n"
                "def usage_line(prog):\n"
                "    width, _ = click.get_terminal_size()\n"
                "    return f'usage: {prog}'[: max(10, min(width, 60))]\n"
            ),
            "test_dispatch.py": (
                "from dispatch import current_args, usage_line\n"
                "\n"
                "\n"
                "def test_explicit_args_passthrough():\n"
                "    assert current_args(['a', 'b']) == ['a', 'b']\n"
                "\n"
                "\n"
                "def test_os_args_shape():\n"
                "    assert isinstance(current_args(), list)\n"
                "\n"
                "\n"
                "def test_usage_line():\n"
                "    assert usage_line('tool').startswith('usage: tool')\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="c04_resultcallback", family=FAMILY, tier=2,
        description="A chained pipeline group aggregating results via Group.resultcallback.",
        migration_points=["Group.resultcallback removed in 8.1 (-> result_callback)"],
        files={
            "pipeline.py": (
                "import click\n"
                "\n"
                "\n"
                "@click.group(chain=True)\n"
                "def cli():\n"
                "    pass\n"
                "\n"
                "\n"
                "@cli.resultcallback()\n"
                "def aggregate(results):\n"
                "    click.echo(f'total={sum(results)}')\n"
                "\n"
                "\n"
                "@cli.command(name='fetch')\n"
                "def fetch():\n"
                "    click.echo('fetched')\n"
                "    return 2\n"
                "\n"
                "\n"
                "@cli.command(name='parse')\n"
                "def parse():\n"
                "    click.echo('parsed')\n"
                "    return 3\n"
            ),
            "test_pipeline.py": (
                "from click.testing import CliRunner\n"
                "\n"
                "from pipeline import cli\n"
                "\n"
                "\n"
                "def test_chain_aggregates():\n"
                "    result = CliRunner().invoke(cli, ['fetch', 'parse'])\n"
                "    assert result.exit_code == 0\n"
                "    assert 'total=5' in result.output\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="c05_completion_multi", family=FAMILY, tier=2,
        description="Two modules sharing completion helpers via autocompletion=.",
        migration_points=["autocompletion= removed on two options in two modules"],
        files={
            "complete.py": (
                "ENVS = ['dev', 'staging', 'prod']\n"
                "\n"
                "\n"
                "def complete_env(ctx, args, incomplete):\n"
                "    return [e for e in ENVS if e.startswith(incomplete)]\n"
            ),
            "app.py": (
                "import click\n"
                "\n"
                "from complete import complete_env\n"
                "\n"
                "\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "\n"
                "\n"
                "@cli.command(name='status')\n"
                "@click.option('--env', autocompletion=complete_env, default='dev')\n"
                "def status(env):\n"
                "    click.echo(f'status:{env}')\n"
                "\n"
                "\n"
                "@cli.command(name='logs')\n"
                "@click.option('--env', autocompletion=complete_env, default='dev')\n"
                "def logs(env):\n"
                "    click.echo(f'logs:{env}')\n"
            ),
            "test_app.py": (
                "from click.testing import CliRunner\n"
                "\n"
                "from app import cli\n"
                "\n"
                "\n"
                "def test_status():\n"
                "    result = CliRunner().invoke(cli, ['status', '--env', 'prod'])\n"
                "    assert result.output.strip() == 'status:prod'\n"
                "\n"
                "\n"
                "def test_logs_default():\n"
                "    result = CliRunner().invoke(cli, ['logs'])\n"
                "    assert result.output.strip() == 'logs:dev'\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="c06_flag_default_help", family=FAMILY, tier=3,
        description="A CLI whose documented help output pins '[default: False]' for a flag.",
        migration_points=[
            "click 8 renders boolean-flag defaults as the flag name ([default: quiet]) — restore the contracted [default: False] (silent output change)",
        ],
        files={
            "serve.py": (
                "import click\n"
                "\n"
                "\n"
                "@click.command()\n"
                "@click.option('--verbose/--quiet', default=False, help='log every request',\n"
                "              show_default=True)\n"
                "def serve(verbose):\n"
                "    click.echo(f'verbose={verbose}')\n"
            ),
            "test_serve.py": (
                "from click.testing import CliRunner\n"
                "\n"
                "from serve import serve\n"
                "\n"
                "\n"
                "def test_runs_quiet_by_default():\n"
                "    result = CliRunner().invoke(serve, [])\n"
                "    assert result.output.strip() == 'verbose=False'\n"
                "\n"
                "\n"
                "def test_help_documents_default_contract():\n"
                "    result = CliRunner().invoke(serve, ['--help'])\n"
                "    assert result.exit_code == 0\n"
                "    assert '[default: False]' in result.output\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="c07_progress_width", family=FAMILY, tier=1,
        description="A progress renderer sized via click.get_terminal_size.",
        migration_points=["click.get_terminal_size removed (-> shutil)"],
        files={
            "progress.py": (
                "import click\n"
                "\n"
                "\n"
                "def bar(fraction):\n"
                "    width, _ = click.get_terminal_size()\n"
                "    width = min(width, 20)\n"
                "    filled = int(round(width * fraction))\n"
                "    return '#' * filled + '-' * (width - filled)\n"
            ),
            "test_progress.py": (
                "from progress import bar\n"
                "\n"
                "\n"
                "def test_full_and_empty():\n"
                "    assert set(bar(1.0)) == {'#'}\n"
                "    assert set(bar(0.0)) == {'-'}\n"
                "\n"
                "\n"
                "def test_length_stable():\n"
                "    assert len(bar(0.5)) == len(bar(0.0)) <= 20\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="c08_group_callback", family=FAMILY, tier=2,
        description="A non-chained group post-processing results via resultcallback, dispatched from get_os_args.",
        migration_points=["Group.resultcallback removed (-> result_callback)",
                          "click.get_os_args removed"],
        files={
            "runner.py": (
                "import click\n"
                "\n"
                "\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "\n"
                "\n"
                "@cli.resultcallback()\n"
                "def stamp(result, **kwargs):\n"
                "    click.echo(f'result={result}')\n"
                "\n"
                "\n"
                "@cli.command(name='count')\n"
                "@click.argument('items', nargs=-1)\n"
                "def count(items):\n"
                "    return len(items)\n"
                "\n"
                "\n"
                "def argv():\n"
                "    return click.get_os_args()\n"
            ),
            "test_runner.py": (
                "from click.testing import CliRunner\n"
                "\n"
                "from runner import argv, cli\n"
                "\n"
                "\n"
                "def test_callback_stamps_result():\n"
                "    result = CliRunner().invoke(cli, ['count', 'a', 'b'])\n"
                "    assert result.exit_code == 0\n"
                "    assert 'result=2' in result.output\n"
                "\n"
                "\n"
                "def test_argv_shape():\n"
                "    assert isinstance(argv(), list)\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="c09_deploy_tool", family=FAMILY, tier=2,
        description="A deploy CLI mixing completion helpers and terminal sizing across modules.",
        migration_points=["autocompletion= removed", "click.get_terminal_size removed (second module)"],
        files={
            "targets.py": (
                "TARGETS = ['blue', 'green', 'canary']\n"
                "\n"
                "\n"
                "def complete_target(ctx, args, incomplete):\n"
                "    return [t for t in TARGETS if t.startswith(incomplete)]\n"
            ),
            "deploy.py": (
                "import click\n"
                "\n"
                "from targets import complete_target\n"
                "\n"
                "\n"
                "def headline(text):\n"
                "    width, _ = click.get_terminal_size()\n"
                "    return text[: max(10, min(width, 30))]\n"
                "\n"
                "\n"
                "@click.command()\n"
                "@click.option('--target', autocompletion=complete_target, default='blue')\n"
                "def deploy(target):\n"
                "    click.echo(headline(f'deploying {target}'))\n"
            ),
            "test_deploy.py": (
                "from click.testing import CliRunner\n"
                "\n"
                "from deploy import deploy\n"
                "\n"
                "\n"
                "def test_deploy_default():\n"
                "    result = CliRunner().invoke(deploy, [])\n"
                "    assert result.exit_code == 0\n"
                "    assert 'deploying blue' in result.output\n"
                "\n"
                "\n"
                "def test_deploy_canary():\n"
                "    result = CliRunner().invoke(deploy, ['--target', 'canary'])\n"
                "    assert 'deploying canary' in result.output\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="c10_cache_flag_help", family=FAMILY, tier=3,
        description="A build tool whose docs pin '[default: False]' for the cache flag.",
        migration_points=[
            "boolean-flag help renders the flag name in click 8 — restore the contracted [default: False] (silent output change)",
        ],
        files={
            "build.py": (
                "import click\n"
                "\n"
                "\n"
                "@click.command()\n"
                "@click.option('--cache/--no-cache', default=False, help='reuse build cache',\n"
                "              show_default=True)\n"
                "def build(cache):\n"
                "    click.echo(f'cache={cache}')\n"
            ),
            "test_build.py": (
                "from click.testing import CliRunner\n"
                "\n"
                "from build import build\n"
                "\n"
                "\n"
                "def test_runs():\n"
                "    assert CliRunner().invoke(build, []).output.strip() == 'cache=False'\n"
                "\n"
                "\n"
                "def test_help_contract():\n"
                "    out = CliRunner().invoke(build, ['--help']).output\n"
                "    assert '[default: False]' in out\n"
            ),
        },
    ))

    return tasks
