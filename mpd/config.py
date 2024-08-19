import os
import re
from pathlib import Path

import ruamel

import llnl.util.tty as tty

import spack.environment as ev
import spack.config
import spack.util.spack_yaml as syaml

from . import util

_DEFAULT_CXXSTD = "17"  # Must be a string for CMake
_NONE_STR = "(none)"


# Pilfered from https://stackoverflow.com/a/568285/3585575
def _process_exists(pid):
    """Check For the existence of a unix pid."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def selected_projects_dir():
    return user_config_dir() / "active"


def selected_projects():
    projects = {}
    for sp in selected_projects_dir().iterdir():
        project_name = sp.read_text()
        projects.setdefault(project_name, []).append(sp.name)
    return projects


def session_id():
    return f"{os.getsid(os.getpid())}"


def selected_project_token():
    return selected_projects_dir() / session_id()


def user_config_dir():
    dir_from_config = spack.config.get('config:mpd_user_dir')
    tty.debug(f"Directory from config is {dir_from_config}")
    if dir_from_config is not None and Path(dir_from_config).exists():
      return Path(dir_from_config).resolve()
    return (Path.home() / ".mpd").resolve()


def mpd_packages():
    return user_config_dir() / "packages"


def user_config_file():
    return user_config_dir() / "config"


def user_config():
    config_file = user_config_file()
    if not config_file.exists():
        return None

    with open(config_file, "r") as f:
        return syaml.load(f)
    return None


def _compiler(variants):
    compiler = None
    compiler_index = None
    for i, variant in enumerate(variants):
        match = re.fullmatch(r"%([\w-]+(@[\d\.]+|/\w+)?)", variant)
        if match:
            compiler = match[1]
            compiler_index = i
            break
    return compiler, compiler_index


def _cxxstd(variants):
    cxx_standard = _DEFAULT_CXXSTD
    cxxstd_index = None
    for i, variant in enumerate(variants):
        # We want to pick out the cxxstd variant for the top-level spec, not any dependencies.
        if variant.startswith("^"):
            break

        match = re.fullmatch(r"cxxstd={1,2}(\d{2})", variant)
        if match:
            cxx_standard = match[1]
            cxxstd_index = i
            break
    return cxx_standard, cxxstd_index


def project_config_from_args(args):
    project = ruamel.yaml.comments.CommentedMap()
    project["name"] = args.name

    top_path = Path(args.top)
    srcs_path = Path(args.srcs) if args.srcs else top_path / "srcs"

    project["top"] = str(top_path.absolute())
    project["source"] = str(srcs_path.absolute())
    project["build"] = str((top_path / "build").absolute())
    project["local"] = str((top_path / "local").absolute())
    project["install"] = str((top_path / "local" / "install").absolute())
    project["envs"] = args.env
    project["deployed"] = _NONE_STR

    packages_to_develop = []
    if srcs_path.exists():
        packages_to_develop = sorted(
            f.name for f in srcs_path.iterdir() if not f.name.startswith(".") and f.is_dir()
        )
    project["packages"] = packages_to_develop

    # Select and remove compiler
    compiler, compiler_index = _compiler(args.variants)
    if compiler_index is not None:
        del args.variants[compiler_index]

    # Select and remove cxxstd
    cxxstd, cxxstd_index = _cxxstd(args.variants)
    if cxxstd_index is not None:
        del args.variants[cxxstd_index]

    if compiler:
        project["compiler"] = compiler
    else:
        tty.warn(f"No compiler spec specified in the variants list, using {_NONE_STR}")
        project["compiler"] = _NONE_STR

    project["cxxstd"] = cxxstd
    project["variants"] = " ".join(args.variants)
    return project


def mpd_project_exists(project_name):
    config_file = user_config_file()
    config = None
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    if config is None:
        return False

    projects = config.get("projects")
    if projects is None:
        return False

    return project_name in projects


def update(project_config, status=None, deployed_env=None):
    config_file = user_config_file()
    config = None
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    if config is None:
        config = ruamel.yaml.comments.CommentedMap()
        config["projects"] = ruamel.yaml.comments.CommentedMap()

    yaml_project_config = ruamel.yaml.comments.CommentedMap()
    yaml_project_config.update(project_config)
    if status:
        yaml_project_config.update(status=status)
    if deployed_env:
        yaml_project_config.update(deployed=deployed_env)
    config["projects"][project_config["name"]] = yaml_project_config

    # Update config file
    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)


def refresh(project_name, new_variants):
    config_file = user_config_file()
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    # Update packages field
    assert config is not None
    assert project_name is not None
    project_cfg = project_config(project_name, config)
    sp = Path(project_cfg["source"])
    assert sp.exists()
    packages_to_develop = sorted(
        f.name for f in sp.iterdir() if not f.name.startswith(".") and f.is_dir()
    )

    # Update .mpd file
    config["projects"][project_name]["packages"] = packages_to_develop

    if new_variants:
        # Select and remove compiler
        compiler, compiler_index = _compiler(new_variants)
        if compiler_index is not None:
            del new_variants[compiler_index]
            config["projects"][project_name]["compiler"] = compiler

        # Select and remove cxxstd
        cxxstd, cxxstd_index = _cxxstd(new_variants)
        if cxxstd_index is not None:
            del new_variants[cxxstd_index]
            config["projects"][project_name]["cxxstd"] = cxxstd

        # Rest of variants
        config["projects"][project_name]["variants"] = " ".join(new_variants)

    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)

    # Return configuration for this project
    return config["projects"][project_name]


def rm_config(project_name):
    config_file = user_config_file()
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    assert config is not None
    assert project_name is not None

    # Remove project entry
    del config["projects"][project_name]
    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)


def project_config(name, config=None):
    if config is None:
        config_file = user_config_file()
        if config_file.exists():
            with open(config_file, "r") as f:
                config = syaml.load(f)

    if config is None:
        print()
        tty.die("Missing MPD configuration.  Please contact scisoft-team@fnal.gov\n")

    projects = config.get("projects")
    if name not in projects:
        print()
        tty.die(
            f"Project '{name}' not supported by MPD configuration."
            " Please contact scisoft-team@fnal.gov\n"
        )

    return projects[name]


def update_cache():
    # Update environment status in user configuration
    config = user_config()
    if not config:
        return

    projects = config.get("projects")
    if not projects:
        return

    adjusted = False
    for name, proj_config in projects.items():
        if not ev.exists(name):
            proj_config["status"] = _NONE_STR
            adjusted = True
        deployed_env = proj_config.get("deployed", _NONE_STR)
        if deployed_env != _NONE_STR and not ev.exists(deployed_env):
            proj_config["deployed"] = _NONE_STR
            adjusted = True

    if adjusted:
        with open(user_config_file(), "w") as f:
            syaml.dump(config, stream=f)

    # Remove stale selected project tokens
    for sp in selected_projects_dir().iterdir():
        if not _process_exists(int(sp.name)):
            sp.unlink()
            continue
        selected_prj = sp.read_text()
        if selected_prj not in projects:
            sp.unlink()

    # Implicitly select project if environment is active
    active_env = ev.active_environment()
    if active_env:
        if active_env.name in projects:
            selected_project_token().write_text(active_env.name)


def selected_project(missing_ok=True):
    token = selected_project_token()
    if token.exists():
        return token.read_text()

    if missing_ok:
        return None

    print()
    tty.die(f"Active MPD project required to invoke '{util.spack_cmd_line()}'\n")


def selected_project_config():
    return project_config(selected_project(missing_ok=False))
