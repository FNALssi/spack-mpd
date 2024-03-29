from enum import Enum

import llnl.util.tty as tty

import spack.environment as ev
import spack.util.spack_yaml as syaml

from . import config
from .util import bold, maybe_with_color


class SelectionStatus(Enum):
    NotSelected = 1
    OnlyThisProcess = 2
    OnlyOtherProcess = 3
    SharedAmongProcesses = 4


def setup_subparser(subparsers):
    lst_description = """list MPD projects

When no arguments are specified, prints a list of existing MPD projects
and their corresponding top-level directories."""
    lst = subparsers.add_parser(
        "list", description=lst_description, aliases=["ls"], help="list MPD projects"
    )
    lst.add_argument(
        "project", metavar="<project name>", nargs="*", help="print details of the MPD project"
    )
    lst.add_argument(
        "-t", "--top", metavar="<project name>", help="print top-level directory for project"
    )


def format_fields(name, selected):
    # Conventions
    #
    # - No color or indicator: not selected for any process
    # - Green, with "▶": selected on only the current process
    # - Cyan, with "◀": selected on other process
    # - Cyan, with "↔": selected on more than one other process
    # - Yellow, with "↔": selected on this process and at least one more other process

    indicator = " "
    color = ""
    warning = ""
    match = selected.get(name)
    if not match:
        return indicator, color, warning

    match_length = len(match)
    assert match_length > 0
    if config.session_id() in match:
        indicator = "▶"
        color = "G" if match_length == 1 else "Y"
    else:
        indicator = "◀"
        color = "c"

    warning = "Warning: used by more than one shell" if match_length > 1 else ""

    return indicator, color, warning


def _no_known_projects():
    tty.msg("No existing MPD projects")


def list_projects():
    cfg = config.user_config()
    if not cfg:
        _no_known_projects()
        return

    projects = cfg.get("projects")
    if not projects:
        _no_known_projects()
        return

    msg = "Existing MPD projects:\n\n"
    name = "Project name"
    name_width = max(len(k) for k in projects.keys())
    name_width = max(len(name), name_width)
    status = "Environment status"
    status_width = len(status)
    msg += f"   {name:<{name_width}}    {status}\n"
    msg += "   " + "-" * name_width + "    " + "-" * status_width

    selected = config.selected_projects()
    for key, value in projects.items():
        status = "active" if ev.active(key) else value["status"]
        indicator, color_code, warning = format_fields(key, selected)
        msg += maybe_with_color(
            color_code,
            f"\n {indicator} {key:<{name_width}}    {status:<{status_width}}  {warning}",
        )
    msg += "\n"
    print()
    tty.msg(msg)


def project_path(project_name, path_kind):
    cfg = config.user_config()
    if not cfg:
        _no_known_projects()
        return

    projects = cfg.get("projects")
    if not projects:
        _no_known_projects()
        return

    if project_name not in projects:
        tty.die(f"No existing MPD project named {bold(project_name)}")

    print(projects[project_name][path_kind])


def project_details(project_names):
    config = user_config()
    if not config:
        _no_known_projects()
        return

    projects = cfg.get("projects")
    if not projects:
        _no_known_projects()
        return

    print()
    for name in project_names:
        if name not in projects:
            tty.warn(f"No existing MPD project named {bold(name)}")
            continue

        msg = f"Details for {bold(name)}\n\n" + syaml.dump_config(projects[name])
        tty.msg(msg)


def process(args):
    if args.project:
        project_details(args.project)
    elif args.top:
        project_path(args.top, "top")
    else:
        list_projects()
