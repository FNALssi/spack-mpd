import llnl.util.tty as tty

from .config import selected_project, project_config, refresh_config
from .new_project import refresh_project


def setup_subparser(subparsers):
    refresh = subparsers.add_parser(
        "refresh", description="refresh project area", help="refresh project area"
    )
    refresh.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="force reconcretization even if sources directory has not changed",
    )


def process(args):
    name = selected_project()
    current_config = project_config(name)
    new_config = refresh_config(name)
    if current_config == new_config and not args.force:
        tty.msg(f"Project {name} is up-to-date")
        return
    refresh_project(name, new_config)
