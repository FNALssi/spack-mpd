import llnl.util.tty as tty

import spack.environment as ev

from . import config, init
from .util import bold, cyan

SUBCOMMAND = "status"


def setup_subparser(subparsers):
    subparsers.add_parser(
        SUBCOMMAND, description="current MPD status on this system", help="current MPD status"
    )


def _environment_status(status_str):
    return f"\n    Environment status: {cyan(status_str)}"


def process(args):
    if not init.initialized():
        tty.warn("MPD not initialized--invoke: " + bold("spack mpd init"))
        return

    selected = config.selected_project_config()
    if not selected:
        tty.info(f"Selected project: {cyan('None')}")
        return

    name = selected["name"]
    msg = f"Selected project: {cyan(name)}"

    env = ev.active_environment()
    if not env:
        tty.info(msg + _environment_status("inactive"))
        return

    if env.path == selected["local"]:
        tty.info(msg + _environment_status("active"))
        return

    tty.info(msg)
    tty.warn(f"An environment is active that does not correspond to the MPD project {cyan(name)}.")
