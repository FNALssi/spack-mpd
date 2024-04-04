import llnl.util.tty as tty
import spack.environment as ev

from .. import clear
from .. import clone
from .. import build
from .. import init
from .. import install
from .. import list_projects
from .. import config
from .. import new_project
from .. import refresh
from .. import rm_project
from .. import select
from .. import util
from .. import test
from .. import zap_build

description = "develop multiple packages using Spack for external software"
section = "scripting"
level = "long"

_VERSION = "0.1.0"


def setup_parser(subparser):
    subparser.add_argument(
        "-V", "--version", action="store_true", help=f"print MPD version ({_VERSION}) and exit"
    )

    subparsers = subparser.add_subparsers(dest="mpd_subcommand", required=False)
    build.setup_subparser(subparsers)
    clear.setup_subparser(subparsers)
    clone.setup_subparser(subparsers)
    init.setup_subparser(subparsers)
    install.setup_subparser(subparsers)
    list_projects.setup_subparser(subparsers)
    new_project.setup_subparser(subparsers)
    refresh.setup_subparser(subparsers)
    rm_project.setup_subparser(subparsers)
    select.setup_subparser(subparsers)
    test.setup_subparser(subparsers)
    zap_build.setup_subparser(subparsers)


def mpd(parser, args):
    if not args.version and not args.mpd_subcommand:
        parser.parse_args(["mpd", "-h"])
        return

    if args.mpd_subcommand == "init":
        init.process(args)
        return

    # Each command below either relies on the cached information in the user
    # configuration or the cached selected project (if it exists).
    config.update_cache()

    if args.mpd_subcommand in ("list", "ls"):
        list_projects.process(args)
        return

    # Each command below requires MPD to be initialized on the system.
    if not init.initialized():
        print()
        tty.die("MPD not initialized on this system.  Invoke\n\n" "  spack mpd init\n")

    # new-project requires no active environment (checks occurs inside
    # new_project.process)
    if args.mpd_subcommand in ("new-project", "n", "newDev"):
        new_project.process(args)
        return

    # select requires no active environment (checks occurs inside
    # select.process)
    if args.mpd_subcommand == "select":
        select.process(args)
        return

    # clear requires no active environment (checks occurs inside
    # clear.process)
    if args.mpd_subcommand == "clear":
        clear.process(args)
        return

    # rm-project requires a deselected project and no active
    # environment (checks occur inside rm_project.process)
    if args.mpd_subcommand in ("rm-project", "rm"):
        rm_project.process(args)
        return

    # Each command below requires a selected project.
    project_name = config.selected_project(missing_ok=False)

    if args.mpd_subcommand in ("git-clone", "g", "gitCheckout"):
        clone.process(args)
        return

    if args.mpd_subcommand == "refresh":
        refresh.process(args)
        return

    if args.mpd_subcommand in ("zap", "z"):
        zap_build.process(args)
        return

    # Each command below requires an active environment
    if not ev.active(project_name):
        print()
        tty.die(
            f"Active environment required to invoke '{util.spack_cmd_line()}'.  Invoke\n\n"
            f"  spack env activate {project_name}\n"
        )

    if args.mpd_subcommand in ("build", "b"):
        build.process(args)
        return
