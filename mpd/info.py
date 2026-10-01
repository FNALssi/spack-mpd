import spack.util.spack_yaml as syaml

from . import config
from .preconditions import State, preconditions
from .spack_compat import tty
from .util import bold

SUBCOMMAND = "info"


def _no_known_projects():
    tty.msg("No existing MPD projects")


def setup_subparser(subparsers):
    info = subparsers.add_parser(
        SUBCOMMAND, description="show MPD project details", help="show MPD project details"
    )
    info.add_argument(
        "project", metavar="<project name>", nargs="*", help="print details of the MPD project"
    )
    info.add_argument(
        "--raw",
        action="store_true",
        help="print YAML configuration of the MPD project (used only with project names)",
    )
    paths = info.add_mutually_exclusive_group()
    paths.add_argument(
        "-t", "--top", metavar="<project name>", help="print top-level directory for project"
    )
    paths.add_argument(
        "-b", "--build", metavar="<project name>", help="print build-level directory for project"
    )
    paths.add_argument(
        "-s", "--source", metavar="<project name>", help="print source-level directory for project"
    )


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

    print(config.canonical_path(projects[project_name][path_kind]))


def project_details(project_names, raw):
    cfg = config.mpd_config()
    if not cfg:
        _no_known_projects()
        return

    projects = cfg.get("projects")
    raw_projects = ((config.mpd_config(raw=True) or {}).get("projects") or {})
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
            tty.msg(preamble + "\n\n" + syaml.dump_config(raw_projects[name]))
            continue

        tty.msg(preamble)
        config.print_config_info(projects[name])
        peers = config.shared_source_peers(name, projects)
        if peers:
            tty.info(f"Shared source with: {', '.join(peers)}")
        print()
    conflicts = config.layout_conflicts(projects)
    if conflicts:
        tty.warn(config.format_conflicts(conflicts))


def process(args):
    preconditions(State.INITIALIZED)

    paths = [(kind, getattr(args, kind)) for kind in ("top", "build", "source")]
    path = next(((kind, name) for kind, name in paths if name), None)
    if args.project and path:
        tty.die("Specify project names or a project directory option, not both")
    if args.raw and path:
        tty.die("--raw cannot be used with a project directory option")
    if args.project:
        project_details(args.project, args.raw)
    elif path:
        project_path(path[1], path[0])
    else:
        tty.die("Specify a project name or a project directory option")
