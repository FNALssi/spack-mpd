import shutil
import subprocess
from pathlib import Path

import llnl.util.tty as tty

import spack.environment as ev

from .config import mpd_packages, rm_config, project_config, selected_project


def setup_subparser(subparsers):
    rm_proj_description = """remove MPD project

Removing a project will:

  * Remove the project entry from the list printed by 'spack mpd list'
  * Delete the 'build' and 'local' directories
  * If '--full' specified, delete the entire 'top' level directory tree of the
    project (including the specified sources directory if it resides
    within the top-level directory).
  * Uninstall the project's package/environment"""
    rm_proj = subparsers.add_parser(
        "rm-project", description=rm_proj_description, aliases=["rm"], help="remove MPD project"
    )
    rm_proj.add_argument("project", metavar="<project name>", help="MPD project to remove")
    rm_proj.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="remove project even if it is selected (environment must be deactivated)",
    )


def _run_no_output(*args):
    return subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _rm_packages(name):
    packages_path = Path(mpd_packages())
    if not packages_path.exists():
        return

    shutil.rmtree(packages_path / f"{name}-bootstrap", ignore_errors=True)


def rm_project(name, config):
    _run_no_output("spack", "env", "rm", "-y", name)
    _rm_packages(name)
    shutil.rmtree(config["build"], ignore_errors=True)
    shutil.rmtree(config["local"], ignore_errors=True)
    rm_config(name)


def process(args):
    msg = ""
    if ev.active(args.project):
        msg = (
            "Must deactivate environment before removing MPD project:\n\n"
            "  spack env deactivate\n"
        )
    if args.project == selected_project() and not args.force:
        msg = (
            "Must deselect MPD project before removing it:\n\n"
            "  spack mpd clear\n\nOr use the --force option.\n"
        )

    if msg:
        print()
        tty.die(msg)

    config = project_config(args.project)
    rm_project(args.project, config)
