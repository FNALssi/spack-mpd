from pathlib import Path

import spack.environment as ev
import spack.llnl.util.tty as tty

from . import config
from .concretize import concretize_project
from .config import print_config_info, selected_project_config
from .preconditions import State, preconditions
from .util import bold, gray

SUBCOMMAND = "refresh"


def setup_subparser(subparsers):
    refresh = subparsers.add_parser(
        SUBCOMMAND,
        description="refresh project using current source directory and specified variants",
        help="refresh project",
    )
    refresh.add_argument(
        "-y", "--yes-to-all", action="store_true", help="Answer yes/default to all prompts"
    )
    refresh.add_argument("variants", nargs="*", help="variants to apply to developed packages")
    refresh.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="force reconcretization even if sources directory has not changed",
    )


def refresh_project(name, project_config, yes_to_all):
    print()

    tty.msg(f"Refreshing project: {bold(name)}")
    print_config_info(project_config)

    if not project_config["packages"]:
        tty.msg(
            "No packages to develop.  You can clone repositories for development by invoking\n\n"
            f"  {gray('>')} spack mpd git-clone --suites <suite name>\n\n"
            "  (or type 'spack mpd git-clone --help' for more options)\n"
        )
        return

    local_env_dir = project_config["local"]
    if ev.is_env_dir(local_env_dir):
        ev.Environment(local_env_dir).destroy()
    Path(local_env_dir).mkdir(exist_ok=True)

    concretize_project(project_config, yes_to_all)


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, ~State.ACTIVE_ENVIRONMENT)

    current_config = selected_project_config()
    name = current_config["name"]
    new_config = config.refresh(name, args.variants)
    if current_config == new_config and not args.force:
        tty.msg(f"Project {bold(name)} is up-to-date")
        return
    refresh_project(name, new_config, args.yes_to_all)
