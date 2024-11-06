import subprocess

import llnl.util.tty as tty

import spack.environment as ev

from .config import selected_project_config
from .preconditions import State, preconditions
from .util import bold, cyan

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
    tty.msg("Installing developed packages with comment:\n\n" + cyan(all_arguments_str) + "\n")

    subprocess.run(all_arguments)

    # Now install the environment
    name = project_config["name"]
    env = ev.read(name)
    with env, env.write_transaction():
        env.install_all()
        env.write()

    print()
    tty.msg(f"The {bold(name)} environment has been installed.\n")


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, State.ACTIVE_ENVIRONMENT)

    install(selected_project_config())
