import llnl.util.tty as tty

from . import config
from .preconditions import State, preconditions
from .util import cyan

SUBCOMMAND = "select"


def setup_subparser(subparsers):
    select = subparsers.add_parser(
        SUBCOMMAND, description="select MPD project", help="select MPD project"
    )
    select.add_argument("project", help="")


def process(args):
    preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)

    cfg = config.mpd_config()
    if not cfg:
        tty.error(f"No existing MPD projects--cannot select {args.project}.")

    projects = cfg.get("projects")
    if not projects:
        tty.error(f"No existing MPD projects--cannot select {args.project}.")

    if args.project not in projects:
        msg = (f"{cyan(args.project)} is not an existing MPD project.  "
               "Choose from:\n")
        for i, key in enumerate(sorted(projects.keys())):
            msg += f"\n {i + 1}) {key}"
        print()
        tty.error(msg + "\n")

    if args.project in config.selected_projects():
        tty.warn(f"Project {cyan(args.project)} selected in another shell.  "
                 "Use with caution.")

    config.selected_project_token().write_text(args.project)
