import os

import llnl.util.tty as tty

import spack.util.spack_yaml as syaml

from .config import user_config
from .util import bold


def setup_subparser(subparsers):
    lst_description = """list MPD projects

When no arguments are specified, prints a list of known MPD projects
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


def _no_known_projects():
    tty.msg("No known MPD projects")


def list_projects():
    config = user_config()
    if not config:
        _no_known_projects()
        return

    projects = config.get("projects")
    if not projects:
        _no_known_projects()
        return

    msg = "Known MPD projects:\n\n"
    name = "Project name"
    name_width = max(len(k) for k in projects.keys())
    name_width = max(len(name), name_width)
    msg += f"   {name:<{name_width}}    Top-level directory\n"
    msg += "   " + "-" * name_width + "    " + "-" * 30

    current_project = os.environ.get("MPD_PROJECT")
    for key, value in projects.items():
        prefix = " "
        if not value["installed"]:
            prefix = "!"
        elif current_project and key == current_project:
            prefix = "*"
        msg += f"\n {prefix} {key:<{name_width}}    {value['top']}"
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
        tty.die(f"No known MPD project named {bold(project_name)}")

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
            tty.warn(f"No known MPD project named {bold(name)}")
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
