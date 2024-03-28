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

    if args.mpd_subcommand in ("build", "b"):
        build.process(args)
        return

    if args.mpd_subcommand == "clear":
        clear.process(args)
        return

    if args.mpd_subcommand in ("git-clone", "g", "gitCheckout"):
        clone.process(args)
        return

    if args.mpd_subcommand == "init":
        init.process(args)
        return

    if args.mpd_subcommand in ("list", "ls"):
        list_projects.process(args)
        return

    if args.mpd_subcommand in ("new-project", "n", "newDev"):
        new_project.process(args)
        return

    if args.mpd_subcommand == "refresh":
        refresh.process(args)
        return

    if args.mpd_subcommand in ("rm-project", "rm"):
        rm_project.process(args)
        return

    if args.mpd_subcommand == "select":
        select.process(args)
        return

    if args.mpd_subcommand in ("zap", "z"):
        zap_build.process(args)
        return


# The following is invoked post-installation
def update(project_config):
    config.update(project_config, status="installed")


# The following is invoked pre-uninstallation
def nullify_status(name):
    prj_config = config.project_config(name)
    config.update(prj_config, status="(none)")
