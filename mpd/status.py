import llnl.util.tty as tty

import spack.environment as ev

from . import config
from .preconditions import State, preconditions
from .util import cyan, gray

SUBCOMMAND = "status"


def setup_subparser(subparsers):
    subparsers.add_parser(
        SUBCOMMAND, description="current MPD status on this system", help="current MPD status"
    )


def _development_status(selected):
    dev_status = selected.get("status", "not concretized")
    return f"\n    Development status: {cyan(dev_status)}"


def _install_status(selected):
    install_status = selected.get("installed", config.UNINSTALLED)
    color = gray if install_status == config.UNINSTALLED else cyan
    return f"\n    Last installed:     {color(install_status)}"


def process(args):
    preconditions(State.INITIALIZED)

    selected = config.selected_project()
    if not selected:
        tty.info(f"Selected project: {cyan('None')}")
        return

    selected = config.project_config(selected)
    name = selected["name"]
    msg = f"Selected project:   {cyan(name)}"
    tty.info(msg + _development_status(selected) + _install_status(selected))

    env = ev.active_environment()
    if env and env.path != selected["local"]:
        tty.warn(
            f"An environment is active that does not correspond to the MPD project {cyan(name)}."
        )
