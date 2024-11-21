import subprocess

import llnl.util.tty as tty

import spack.environment as ev

from .config import selected_project_config
from .preconditions import State, activate_development_environment, preconditions
from .util import bold, cyan, gray

SUBCOMMAND = "install"
ALIASES = ["i"]


def setup_subparser(subparsers):
    subparsers.add_parser(
        SUBCOMMAND,
        description="install (and build if necessary) repositories",
        aliases=ALIASES,
        help="install built repositories",
    )


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, State.PACKAGES_TO_DEVELOP)

    project_config = selected_project_config()
    activate_development_environment(project_config["local"])

    all_arguments = ["cmake", "--install", project_config["build"]]
    all_arguments_str = " ".join(all_arguments)

    print()
    tty.msg("Installing developed packages with command:\n\n" + cyan(all_arguments_str) + "\n")

    stdout = None if args.verbose else subprocess.DEVNULL
    subprocess.run(all_arguments, stdout=stdout)

    tty.msg(gray("Installing environment"))
    # Now install the environment
    name = project_config["name"]
    env = ev.read(name)
    with env, env.write_transaction():
        env.install_all()
        env.write()

    print()
    tty.msg(f"The {bold(name)} environment has been installed.\n")
