import llnl.util.tty as tty

import spack.environment as ev

from . import init
from . import config
from .util import bold


SUBCOMMAND = "status"


def setup_subparser(subparsers):
    subparsers.add_parser(
        SUBCOMMAND, description="current MPD status on this system", help="current MPD status"
    )


def process(args):
    if not init.initialized():
        tty.warn("MPD not initialized--invoke: " + bold("spack mpd init"))
        return

    selected = config.selected_project()
    bold_selected = bold(selected) if selected else bold("None")
    msg = f"Selected project: {bold_selected}"
    if selected:
        cfg = config.selected_project_config()
        status = bold("active") if ev.active(selected) else cfg["status"]
        msg += f"\n    Environment status: {status}"
    tty.info(msg)
