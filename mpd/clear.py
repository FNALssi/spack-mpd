from . import config
from .preconditions import preconditions, State

SUBCOMMAND = "clear"


def setup_subparser(subparsers):
    subparsers.add_parser(
        SUBCOMMAND, description="clear selected MPD project", help="clear selected MPD project"
    )


def process(args):
    preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)
    config.selected_project_token().unlink(missing_ok=True)
