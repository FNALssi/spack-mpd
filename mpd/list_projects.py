import os
from pathlib import Path

import llnl.util.tty as tty

import spack.util.spack_yaml as syaml

from .mpd_config import mpd_config_file
from .util import bold


def _mpd_config():
    config_file = mpd_config_file()
    if not config_file.exists():
        return None

    with open(config_file, "r") as f:
        return syaml.load(f)
    return None


def _no_known_projects():
    tty.msg(f"No known MPD projects")


def list_projects():
    mpd_config = _mpd_config()
    if not mpd_config:
        _no_known_projects()
        return

    projects = mpd_config.get("projects")
    if not projects:
        _no_known_projects()
        return

    msg = "Known MPD projects:\n\n"
    name = "Project name"
    name_width = max(len(k) for k in projects.keys())
    name_width = max(len(name), name_width)
    msg += f"  {name:<{name_width}}    Top-level directory\n"
    msg += "  " + "-" * name_width + "    " + "-" * 30

    current_project = os.environ.get("MPD_PROJECT")
    for key, value in projects.items():
        active = "*" if current_project and key == current_project else " "
        msg += f"\n {active}{key:<{name_width}}    {value['top']}"
    msg += "\n"
    print()
    tty.msg(msg)


def project_path(project_name, path_kind):
    mpd_config = _mpd_config()
    if not mpd_config:
        _no_known_projects()
        return

    projects = mpd_config.get("projects")
    if not projects:
        _no_known_projects()
        return

    if project_name not in projects:
        tty.die(f"No known MPD project named {bold(project_name)}")

    print(projects[project_name][path_kind])


def project_details(project_names):
    mpd_config = _mpd_config()
    if not mpd_config:
        _no_known_projects()
        return

    projects = mpd_config.get("projects")
    if not projects:
        _no_known_projects()
        return

    print()
    for name in project_names:
        if name not in projects:
            tty.warn(f"No known MPD project named {bold(name)}")
            continue

        msg = f"Details for {bold(name)}\n\n" + syaml.dump_config(projects[name])
        tty.msg(msg)
