import llnl.util.filesystem as fs

from .preconditions import preconditions, State
from .config import selected_project_config


SUBCOMMAND = "zap"
ALIASES = ["z"]


def setup_subparser(subparsers):
    zap_parser = subparsers.add_parser(
        SUBCOMMAND,
        description="delete everything in your build and/or install areas.\n\n"
        "If no optional argument is provided, the '--build' option is assumed.",
        aliases=ALIASES,
        help="delete everything in your build and/or install areas",
    )
    zap = zap_parser.add_mutually_exclusive_group()
    zap.add_argument(
        "--all",
        dest="zap_all",
        action="store_true",
        help="delete everything in your build and install directories",
    )
    zap.add_argument(
        "--build",
        dest="zap_build",
        action="store_true",
        default=True,
        help="delete everything in your build directory",
    )
    zap.add_argument(
        "--install",
        dest="zap_install",
        action="store_true",
        help="delete everything in your install directory",
    )


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT)

    config = selected_project_config()
    if args.zap_install:
        fs.remove_directory_contents(config["install"])
    if args.zap_all:
        fs.remove_directory_contents(config["install"])
        fs.remove_directory_contents(config["build"])
    if args.zap_build:
        fs.remove_directory_contents(config["build"])
