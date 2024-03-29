import llnl.util.tty as tty

import spack.environment as ev

from . import config
from .util import bold


def setup_subparser(subparsers):
    select = subparsers.add_parser(
        "select", description="select MPD project", help="select MPD project"
    )
    select.add_argument("project", help="")


def process(args):
    cfg = config.user_config()
    if not cfg:
        tty.error(f"No existing MPD projects--cannot select {args.project}.")

    projects = cfg.get("projects")
    if not projects:
        tty.error(f"No existing MPD projects--cannot select {args.project}.")

    if args.project not in projects:
        msg = f"{bold(args.project)} is not an existing MPD project.  Choose from:\n"
        for i, key in enumerate(projects.keys()):
            msg += f"\n {i + 1}) {key}"
        print()
        tty.error(msg + "\n")

    env_active = ev.active_environment()
    if env_active:
        print()
        tty.die(
            f"Must deactivate environment {bold(env_active.name)} before selecting project:\n\n"
            "  spack env deactivate\n"
        )

    if args.project in config.selected_projects():
        tty.warn(f"Project {bold(args.project)} selected in another shell.  Use with caution.")

    config.selected_project_token().write_text(args.project)
