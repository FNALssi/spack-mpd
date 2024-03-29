import llnl.util.tty as tty

import spack.environment as ev
import spack.util.spack_yaml as syaml

from .config import user_config, selected_project
from .util import bold, maybe_with_color


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


def format_fields(name, status, selected):
    if selected != name:
        return " ", "", status

    if ev.active(name):
        return "→", "G", "active"

    return "→", "Y", status


def _no_known_projects():
    tty.msg("No existing MPD projects")


def list_projects():
    config = user_config()
    if not config:
        _no_known_projects()
        return

    projects = config.get("projects")
    if not projects:
        _no_known_projects()
        return

    msg = "Existing MPD projects:\n\n"
    name = "Project name"
    name_width = max(len(k) for k in projects.keys())
    name_width = max(len(name), name_width)
    msg += f"   {name:<{name_width}}    Environment status\n"
    msg += "   " + "-" * name_width + "    " + "-" * 30

    selected = selected_project()
    for key, value in projects.items():
        indicator, color_code, status = format_fields(key, value["status"], selected)
        msg += maybe_with_color(color_code, f"\n {indicator} {key:<{name_width}}    {status}")
    msg += "\n"
    print()
    tty.msg(msg)


def project_path(project_name, path_kind):
    config = user_config()
    if not config:
        _no_known_projects()
        return

    projects = config.get("projects")
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

    projects = config.get("projects")
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
