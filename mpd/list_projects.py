import llnl.util.tty as tty

import spack.util.spack_yaml as syaml

from . import config
from .preconditions import State, preconditions
from .util import bold, cyan, maybe_with_color

SUBCOMMAND = "list"
ALIASES = ["ls"]


def setup_subparser(subparsers):
    lst_description = """list MPD projects

When no arguments are specified, prints a list of existing MPD projects
and the status of their corresponding Spack environments."""
    lst = subparsers.add_parser(
        SUBCOMMAND, description=lst_description, aliases=ALIASES, help="list MPD projects"
    )
    lst.add_argument(
        "project", metavar="<project name>", nargs="*", help="print details of the MPD project"
    )
    lst.add_argument("--raw",
                     action="store_true",
                     help="print YAML configuration of the MPD project\n"
                          "(used only when project name is provided)")
    lst_path = lst.add_mutually_exclusive_group()
    lst_path.add_argument(
        "-t", "--top", metavar="<project name>", help="print top-level directory for project"
    )
    lst_path.add_argument(
        "-b", "--build", metavar="<project name>", help="print build-level directory for project"
    )
    lst_path.add_argument(
        "-s", "--source", metavar="<project name>", help="print source-level directory for project"
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
    cfg = config.mpd_config()
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
    location = "Sources directory"
    location_width = max(len(v["source"]) for v in projects.values())
    location_width = max(len(location), location_width)
    msg += f"   {name:<{name_width}}    {location}\n"
    msg += "   " + "-" * name_width + "    " + "-" * location_width

    selected = config.selected_projects()
    for key, value in sorted(projects.items()):
        indicator, color_code, warning = format_fields(key, selected)
        msg += maybe_with_color(
            color_code,
            f"\n {indicator} {key:<{name_width}}    {value['source']:<{location_width}} {warning}"
        )
    msg += f"\n\nType {cyan('spack mpd ls <project name>')} for more details about a project.\n"
    print()
    tty.msg(msg)


def project_path(project_name, path_kind):
    cfg = config.mpd_config()
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


def project_details(project_names, raw):
    cfg = config.mpd_config()
    if not cfg:
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
        preamble = f"Details for {bold(name)}"
        if raw:
            tty.msg(preamble + "\n\n" + syaml.dump_config(projects[name]))
            continue

        tty.msg(preamble)
        config.print_config_info(projects[name])
        print()


def process(args):
    preconditions(State.INITIALIZED)

    if args.project:
        project_details(args.project, args.raw)
    elif args.top:
        project_path(args.top, "top")
    elif args.build:
        project_path(args.build, "build")
    elif args.source:
        project_path(args.source, "source")
    else:
        list_projects()
