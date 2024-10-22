import llnl.util.tty as tty

from . import config
from .new_project import refresh_project
from .preconditions import State, preconditions
from .util import bold

SUBCOMMAND = "refresh"


def setup_subparser(subparsers):
    refresh = subparsers.add_parser(
        SUBCOMMAND,
        description="refresh project using current source directory and specified variants",
        help="refresh project",
    )
    refresh.add_argument("-y", "--yes-to-all",
                         action="store_true",
                         help="Answer yes/default to all prompts")
    refresh.add_argument("variants", nargs="*", help="variants to apply to developed packages")
    refresh.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="force reconcretization even if sources directory has not changed",
    )


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, ~State.ACTIVE_ENVIRONMENT)

    name = config.selected_project()
    current_config = config.project_config(name)
    new_config = config.refresh(name, args.variants)
    if current_config == new_config and not args.force:
        tty.msg(f"Project {bold(name)} is up-to-date")
        return
    refresh_project(name, new_config, args.yes_to_all)
