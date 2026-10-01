import shutil
import subprocess
from pathlib import Path

from . import config as mpd_config
from .config import project_config, rm_config
from .preconditions import State, preconditions
from .spack_compat import ev, tty

SUBCOMMAND = "rm-project"
ALIASES = ["rm"]


def setup_subparser(subparsers):
    rm_proj_description = """remove MPD project

Removing a project will:

  * Remove the project entry from the list printed by 'spack mpd list'
  * Delete the 'build', 'local', and '.mpd' directories when safe
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


def rm_project(name, config, cleanup=True):
    if not cleanup:
        rm_config(name)
        mpd_config.clear_project_selections(name)
        return

    if ev.is_env_dir(config["local"]):
        subprocess.run(
            ["spack", "env", "rm", "-y", config["local"]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    for path in (config["build"], config["local"], Path(config["top"]) / ".mpd"):
        shutil.rmtree(path, ignore_errors=True)
    rm_config(name)
    mpd_config.clear_project_selections(name)


def process(args):
    if args.force:
        preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)
    else:
        preconditions(State.INITIALIZED, ~State.SELECTED_PROJECT, ~State.ACTIVE_ENVIRONMENT)

    config = project_config(args.project)
    cfg = mpd_config.mpd_config()
    conflicts = mpd_config.removal_conflicts(args.project, cfg["projects"])
    if conflicts:
        paths = mpd_config.project_paths(config)
        preserved = "\n".join(f" - {paths[role]}" for role in mpd_config.PROTECTED_ROLES)
        tty.warn(
            f"Unregistering MPD project '{args.project}' without deleting managed paths because "
            f"they overlap another project. Manual cleanup may be required.\n{preserved}\n\n"
            + mpd_config.format_conflicts(conflicts)
        )
        rm_project(args.project, config, cleanup=False)
        return
    rm_project(args.project, config)
