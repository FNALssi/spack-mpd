from pathlib import Path

import llnl.util.tty as tty

from . import config
from .preconditions import State, preconditions
from .util import cyan, get_number, gray

SUBCOMMAND = "select"


def setup_subparser(subparsers):
    select_description = f"""An MPD project must be selected for doing development work.
This can be done in one of three ways:

  {gray(">")} spack mpd select
      {gray("(select project from user prompt)")}

  {gray(">")} spack mpd select <top-level directory of project>
      {gray("(select project given its top-level directory)")}

  {gray(">")} spack mpd select -p <project name>
      {gray("(select project given its name)")}
"""
    select = subparsers.add_parser(
        SUBCOMMAND, description=select_description, help="select MPD project"
    )
    select = select.add_mutually_exclusive_group()
    select.add_argument("directory",
                        nargs="?",
                        help="can specify top-level directory of the project")
    select.add_argument("-p", "--project",
                        metavar="<project name>",
                        help="select project with name")


def select_from_prompt(projects, error_msg=None):
    print()
    if error_msg:
        tty.error(error_msg)

    msg = "Available MPD projects:\n"
    numbered_projects = {}
    num_projects = len(projects)
    for i, key in enumerate(sorted(projects.keys())):
        numbered_projects[i + 1] = key
        msg += f"\n {i + 1}) {key}"
    tty.info(msg + "\n")
    project_number = 0
    while project_number == 0:
        project_number = get_number("Select a project (type the number): ")
        if project_number > num_projects:
            tty.warn(f"Pick a number between {1} and {num_projects}")
            project_number = 0
    return numbered_projects[project_number]


def process(args):
    preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)

    cfg = config.mpd_config()
    if not cfg:
        tty.error(f"No existing MPD projects--cannot select {args.project}.")

    projects = cfg.get("projects")
    if not projects:
        tty.error(f"No existing MPD projects--cannot select {args.project}.")

    directory = args.directory
    project = args.project
    # If no arguments are provided, then either select the project automatically, or go
    # through the project menu.
    if not directory and not project:
        if len(projects) == 1:
            # Automatically select the project if there is only one
            project = list(projects.keys())[0]
        else:
            project = select_from_prompt(projects)

    # Top-level directory specified - find the corresponding projects
    if directory and not project:
        absolute_dir = Path(directory).resolve()
        for pname, pconfig in projects.items():
            if str(absolute_dir) == pconfig.get("top"):
                project = pname
        if project is None:
            tty.die(f"Could not select project with top-level directory {absolute_dir}")

    # Project name specified
    if project not in projects:
        project = select_from_prompt(projects,
                                     error_msg=f"{cyan(project)} is not an existing MPD project")

    if project == config.selected_project():
        tty.info(f"Project {cyan(project)} already selected")
        return

    if project in config.selected_projects():
        tty.warn(f"Project {cyan(project)} selected in another shell.  "
                 "Use with caution.")

    config.selected_project_token().write_text(project)
    tty.info(f"Project {cyan(project)} selected")
