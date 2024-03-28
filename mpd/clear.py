from .config import selected_project_token


def setup_subparser(subparsers):
    subparsers.add_parser(
        "clear", description="clear selected MPD project", help="clear selected MPD project"
    )


def process(args):
    selected_project_token().unlink(missing_ok=True)
