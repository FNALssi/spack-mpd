import llnl.util.tty as tty

import spack.environment as ev

from . import config
from .util import bold


def setup_subparser(subparsers):
    subparsers.add_parser(
        "clear", description="clear selected MPD project", help="clear selected MPD project"
    )


def process(args):
    env_active = ev.active_environment()
    if env_active:
        print()
        tty.die(
            f"Must deactivate environment {bold(env_active.name)} before clearing project:\n\n"
            "  spack env deactivate\n"
        )

    config.selected_project_token().unlink(missing_ok=True)
