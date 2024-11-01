import subprocess

import llnl.util.tty as tty

import spack
import spack.environment as ev
import spack.store

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
    packages = project_config["packages"]
    local_env_dir = project_config["local"]
    assert ev.is_env_dir(local_env_dir)
    env = ev.Environment(local_env_dir)
    developed_specs = [s for s in env.all_specs() if s.name in packages]
    for s in developed_specs:
        spack.store.STORE.layout.create_install_directory(s)

    all_arguments = ["cmake", "--install", project_config["build"]]
    all_arguments_str = " ".join(all_arguments)

    print()
    tty.msg("Installing with command:\n\n" + cyan(all_arguments_str) + "\n")

    subprocess.run(all_arguments)

    for s in developed_specs:
        spack.store.STORE.db.add(s)


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, State.ACTIVE_ENVIRONMENT)

    install(selected_project_config())
