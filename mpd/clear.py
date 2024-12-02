import llnl.util.tty as tty

from . import config
from .preconditions import State, preconditions
from .util import maybe_with_color

SUBCOMMAND = "clear"


def setup_subparser(subparsers):
    clear = subparsers.add_parser(
        SUBCOMMAND, description="clear selected MPD project", help="clear selected MPD project"
    )
    clear.add_argument(
        "--all",
        action="store_true",
        help="clear all selected MPD projects\n"
        + maybe_with_color("y", "(Warning: will clear selected projects in other shells)"),
    )


def process(args):
    preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)
    if args.all:
        for p in config.selected_projects_dir().iterdir():
            p.unlink(missing_ok=True)
        tty.warn("All MPD projects in all shells have been cleared.")
    else:
        config.selected_project_token().unlink(missing_ok=True)
