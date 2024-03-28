import llnl.util.tty as tty

from .config import selected_project_token, update_cached_configs, user_config
from .util import bold


def setup_subparser(subparsers):
    select = subparsers.add_parser(
        "select", description="select MPD project", help="select MPD project"
    )
    select.add_argument("project", help="")


def process(args):
    update_cached_configs()

    config = user_config()
    if not config:
        tty.error(f"No existing MPD projects--cannot select {args.project}.")

    projects = config.get("projects")
    if not projects:
        tty.error(f"No existing MPD projects--cannot select {args.project}.")

    if args.project not in projects:
        msg = f"{bold(args.project)} is not an existing MPD project.  Choose from:\n"
        for i, key in enumerate(projects.keys()):
            msg += f"\n {i + 1}) {key}"
        print()
        tty.error(msg + "\n")

    selected_project_token().write_text(args.project)
