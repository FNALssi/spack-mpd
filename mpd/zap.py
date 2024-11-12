import llnl.util.filesystem as fs

import spack.environment as ev
import spack.package_base

from .config import selected_project_config
from .preconditions import State, preconditions

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
        dest="zap",
        action="store_true",
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

    project_config = selected_project_config()

    # Default is to zap build only
    zap_only = args.zap or not (args.zap_all or args.zap or args.zap_install)
    if zap_only:
        fs.remove_directory_contents(project_config["build"])
        return

    if args.zap_all:
        fs.remove_directory_contents(project_config["build"])

    packages = project_config["packages"]
    env = ev.read(project_config["name"])
    developed_specs = [s for s in env.all_specs() if s.name in packages]

    for s in developed_specs:
        if not s.installed:
            continue
        spack.package_base.PackageBase.uninstall_by_spec(s, force=True)
