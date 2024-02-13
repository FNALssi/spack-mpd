from pathlib import Path

import llnl.util.tty as tty

import spack.util.spack_yaml as syaml


def _mrb_config():
    home_dir = Path.home()
    config_file = home_dir / ".mrb"
    if not config_file.exists():
        return None

    with open(config_file, "r") as f:
        return syaml.load(f)
    return None


def _no_known_projects():
    tty.msg(f"No known MRB projects")


def list_projects():
    mrb_config = _mrb_config()
    if not mrb_config:
        _no_known_projects()

    projects = mrb_config.get("projects")
    if not projects:
        _no_known_projects()

    msg = "Known MRB projects:\n\n"
    name = "Project name"
    name_width = max(len(k) for k in projects.keys())
    name_width = max(len(name), name_width)
    msg += f"  {name:<{name_width}}    Top-level directory\n"
    msg += "  " + "-" * name_width + "    " + "-" * 30

    for key, value in projects.items():
        msg += f"\n  {key:<{name_width}}    {value['top']}"
    msg += "\n"
    print()
    tty.msg(msg)


def project_path(project_name, path_kind):
    mrb_config = _mrb_config()
    if not mrb_config:
        _no_known_projects()

    projects = mrb_config.get("projects")
    if not projects:
        _no_known_projects()

    boldname = tty.color.colorize("@*{" + project_name + "}")
    if project_name not in projects:
        tty.die(f"No known MRB project named {boldname}")

    print(projects[project_name][path_kind])


def project_details(project_names):
    mrb_config = _mrb_config()
    if not mrb_config:
        _no_known_projects()

    projects = mrb_config.get("projects")
    if not projects:
        _no_known_projects()

    print()
    for name in project_names:
        boldname = tty.color.colorize("@*{" + name + "}")
        if name not in projects:
            tty.warn(f"No known MRB project named {boldname}")
            continue

        msg = f"Details for {boldname}\n\n" + syaml.dump_config(projects[name])
        tty.msg(msg)
