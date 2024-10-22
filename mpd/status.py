import llnl.util.tty as tty

import spack.environment as ev

from . import config, init
from .util import bold, cyan

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
    is_selected = cyan(selected) if selected else cyan("None")
    msg = f"Selected project: {cyan(is_selected)}"
    if selected:
        cfg = config.selected_project_config()
        status = "active" if ev.active(selected) else cfg["status"]
        msg += f"\n    Environment status: {cyan(status)}"
    tty.info(msg)
