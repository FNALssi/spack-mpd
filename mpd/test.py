import subprocess

import llnl.util.tty as tty

import spack.environment as ev
import spack.environment.shell as ev_shell

from .config import selected_project_config
from .preconditions import State, preconditions
from .util import maybe_with_color

SUBCOMMAND = "test"
ALIASES = ["t"]


def setup_subparser(subparsers):
    test = subparsers.add_parser(
        SUBCOMMAND, description="build and run tests", aliases=ALIASES, help="build and run tests"
    )
    test.add_argument(
        "-j",
        dest="parallel",
        metavar="<number>",
        help="specify number of threads for invoking ctest",
    )
    test.add_argument(
        "test_options",
        metavar="-- <test options>",
        nargs="*",
        help="options passed directly to generator",
    )


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT)

    config = selected_project_config()
    build_dir = config["build"]

    arguments = ["ctest", "--test-dir", build_dir]
    if args.parallel:
        arguments.append(f"-j{args.parallel}")

    arguments += args.test_options

    arguments_str = " ".join(arguments)
    print()
    tty.msg("Testing with command:\n\n" + maybe_with_color("c", arguments_str) + "\n")

    development_env = ev.Environment(config["local"])
    ev_shell.activate(development_env).apply_modifications()
    subprocess.run(arguments)
