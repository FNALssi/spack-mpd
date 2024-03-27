import llnl.util.tty as tty

from .config import active_project, project_config, refresh_config
from .new_project import update_project


def setup_subparser(subparsers):
    subparsers.add_parser(
        "refresh", description="refresh project area", help="refresh project area"
    )


def process(args):
    name = active_project()
    current_config = project_config(name)
    new_config = refresh_config(name)
    if current_config == new_config:
        tty.msg(f"Project {name} is up-to-date")
        return
    update_project(name, new_config)
