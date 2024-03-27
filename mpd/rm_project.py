import os
import shutil
import subprocess
from pathlib import Path

import llnl.util.tty as tty

from .config import mpd_packages, rm_config, project_config
from .util import bold


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
        "--full",
        action="store_true",
        help="remove entire directory tree starting at the top level of the project",
    )


def _run_no_output(*args):
    return subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _rm_packages(name):
    packages_path = Path(mpd_packages())
    if not packages_path.exists():
        return

    shutil.rmtree(packages_path / f"{name}-bootstrap", ignore_errors=True)
    shutil.rmtree(packages_path / f"{name}-mpd", ignore_errors=True)


def rm_project(name, config, full_removal):
    _run_no_output("spack", "env", "rm", "-y", name)
    _run_no_output("spack", "uninstall", "-y", f"{name}-mpd")
    _rm_packages(name)
    shutil.rmtree(config["build"], ignore_errors=True)
    shutil.rmtree(config["local"], ignore_errors=True)
    if full_removal:
        shutil.rmtree(config["top"], ignore_errors=True)
    rm_config(name)


def process(args):
    config = project_config(args.project)
    if args.project == os.environ.get("MPD_PROJECT"):
        print()
        tty.die(
            f"Cannot remove active MPD project {bold(args.project)}.  Deactivate by invoking:"
            "\n\n"
            "           spack env deactivate\n"
        )
    rm_project(args.project, config, args.full)
