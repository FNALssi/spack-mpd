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
from .. import status
from .. import test
from .. import zap_build

description = "develop multiple packages using Spack for external software"
section = "scripting"
level = "long"

_VERSION = "0.1.0"

subcommands = [
    "build",
    "clear",
    "clone",
    "init",
    "install",
    "list_projects",
    "new_project",
    "refresh",
    "rm_project",
    "select",
    "status",
    "test",
    "zap_build",
]


def setup_parser(subparser):
    subparser.add_argument(
        "-V", "--version", action="store_true", help=f"print MPD version ({_VERSION}) and exit"
    )

    subparsers = subparser.add_subparsers(dest="mpd_subcommand", required=False)
    for name in subcommands:
        globals()[name].setup_subparser(subparsers)


def mpd(parser, args):
    for name in subcommands:
        m = globals()[name]
        scmds = [m.SUBCOMMAND] + getattr(m, "ALIASES", [])
        if args.mpd_subcommand not in scmds:
            continue

        if args.mpd_subcommand != "init":
            # Each non-init command either relies on the cached
            # information in the user configuration or the cached
            # selected project (if it exists).
            config.update_cache()

        m.process(args)
        break
