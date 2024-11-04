import subprocess

import llnl.util.tty as tty

from .config import selected_project_config
from .preconditions import State, preconditions
from .util import cyan

SUBCOMMAND = "install"
ALIASES = ["i"]


def setup_subparser(subparsers):
    subparsers.add_parser(
        SUBCOMMAND,
        description="install (and build if necessary) repositories",
        aliases=ALIASES,
        help="install built repositories",
    )


def install(project_config):

    all_arguments = ["cmake", "--install", project_config["build"]]
    all_arguments_str = " ".join(all_arguments)

    print()
    tty.msg("Installing with command:\n\n" + cyan(all_arguments_str) + "\n")

    subprocess.run(all_arguments)


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, State.ACTIVE_ENVIRONMENT)

    install(selected_project_config())
