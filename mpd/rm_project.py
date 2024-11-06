import shutil
import subprocess

from .config import project_config, rm_config
from .preconditions import State, preconditions

SUBCOMMAND = "rm-project"
ALIASES = ["rm"]


def setup_subparser(subparsers):
    rm_proj_description = """remove MPD project

Removing a project will:

  * Remove the project entry from the list printed by 'spack mpd list'
  * Delete the 'build' and 'local' directories
  * Uninstall the project's environment"""
    rm_proj = subparsers.add_parser(
        SUBCOMMAND, description=rm_proj_description, aliases=ALIASES, help="remove MPD project"
    )
    rm_proj.add_argument("project", metavar="<project name>", help="MPD project to remove")
    rm_proj.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="remove project even if it is selected (environment must be deactivated)",
    )


def rm_project(name, config):
    subprocess.run(["spack", "env", "rm", "-y", config["local"]],
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    shutil.rmtree(config["build"], ignore_errors=True)
    rm_config(name)


def process(args):
    if args.force:
        preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)
    else:
        preconditions(State.INITIALIZED, ~State.SELECTED_PROJECT, ~State.ACTIVE_ENVIRONMENT)

    config = project_config(args.project)
    rm_project(args.project, config)
