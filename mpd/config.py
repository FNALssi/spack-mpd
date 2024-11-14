import os
import re
from pathlib import Path

import ruamel

import llnl.util.tty as tty

import spack.environment as ev
import spack.util.spack_yaml as syaml

from . import init
from .util import cyan, spack_cmd_line

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


def mpd_config_dir():
    return init.mpd_config_dir()


def mpd_config_file():
    return init.mpd_config_file(mpd_config_dir())


def selected_projects_dir():
    return init.mpd_selected_projects_dir(mpd_config_dir())


def selected_projects():
    projects = {}
    for sp in selected_projects_dir().iterdir():
        project_name = sp.read_text()
        projects.setdefault(project_name, []).append(sp.name)
    return projects


def session_id():
    return f"{os.getsid(os.getpid())}"


def selected_project_token():
    projects_dir = selected_projects_dir()
    return projects_dir / session_id() if projects_dir else None


def mpd_config():
    config_file = mpd_config_file()
    if not config_file.exists():
        return None

    with open(config_file, "r") as f:
        return syaml.load(f)
    return None


def parse_for_variant(pattern, variants, default=None):
    for i, variant in enumerate(variants):
        # We want to pick out the cxxstd variant for the top-level spec, not any dependencies.
        if variant.startswith("^"):
            break

        match = re.fullmatch(pattern, variant)
        if match:
            return match[1], i

    return default, None


def _compiler(variants):
    return parse_for_variant(r"%([\w-]+(@[\d\.]+|/\w+)?)", variants)


def _cxxstd(variants):
    return parse_for_variant(r"cxxstd={1,2}(\d{2})", variants, default=_DEFAULT_CXXSTD)


def _generator(variants):
    value, index = parse_for_variant(r"generator=(\w+)", variants, default="make")
    if value == "make":
        return "Unix Makefiles", index
    if value == "ninja":
        return "Ninja", index
    tty.die(f"Only 'make' and 'ninja' generators are allowed (specified {value}).")


def prepare_project_directories(top_path, srcs_path):
    def _create_dir(path):
        path.mkdir(exist_ok=True)
        return str(path.absolute())

    return {"top": _create_dir(top_path),
            "source": _create_dir(srcs_path),
            "build": _create_dir(top_path / "build"),
            "local": _create_dir(top_path / "local")}


def handle_variants(project_cfg, variants):
    # Select and remove compiler
    compiler, compiler_index = _compiler(variants)
    if compiler_index is not None:
        del variants[compiler_index]

    if compiler is None:
        if "compiler" not in project_cfg:
            tty.warn(f"No compiler spec specified in the variants list, using {_NONE_STR}")
            project_cfg["compiler"] = _NONE_STR
    else:
        project_cfg["compiler"] = compiler

    # Select and remove cxxstd
    cxxstd, cxxstd_index = _cxxstd(variants)
    if cxxstd_index is not None:
        del variants[cxxstd_index]

    if cxxstd_index is None:
        if "cxxstd" not in project_cfg:
            project_cfg["cxxstd"] = cxxstd
    else:
        project_cfg["cxxstd"] = cxxstd

    # Select and remove generator
    generator, generator_index = _generator(variants)
    if generator_index is not None:
        del variants[generator_index]

    if generator:
        project_cfg["generator"] = generator

    if variants:
        project_cfg["variants"] = " ".join(variants)

    return project_cfg


def project_config_from_args(args):
    project = ruamel.yaml.comments.CommentedMap()
    project["name"] = args.name
    project["envs"] = args.env

    top_path = Path(args.top)
    srcs_path = Path(args.srcs) if args.srcs else top_path / "srcs"

    directories = prepare_project_directories(top_path, srcs_path)
    project.update(directories)
    assert srcs_path.exists()
    packages_to_develop = sorted(
        f.name for f in srcs_path.iterdir() if not f.name.startswith(".") and f.is_dir()
    )
    project["packages"] = packages_to_develop
    return handle_variants(project, args.variants)


def mpd_project_exists(project_name):
    config_file = mpd_config_file()
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


def update(project_config, status=None):
    config_file = mpd_config_file()
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
    config["projects"][project_config["name"]] = yaml_project_config

    # Update config file
    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)


def refresh(project_name, new_variants):
    config_file = mpd_config_file()
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    # Update packages field
    assert config is not None
    assert project_name is not None
    project_cfg = project_config(project_name, config)

    top_path = Path(project_cfg["top"])
    srcs_path = Path(project_cfg["source"])

    prepare_project_directories(top_path, srcs_path)
    assert srcs_path.exists()
    packages_to_develop = sorted(
        f.name for f in srcs_path.iterdir() if not f.name.startswith(".") and f.is_dir()
    )
    project_cfg["packages"] = packages_to_develop

    config[project_name] = handle_variants(project_cfg, new_variants)
    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)

    # Return configuration for this project
    return config[project_name]


def rm_config(project_name):
    config_file = mpd_config_file()
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
        config_file = mpd_config_file()
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
    config = mpd_config()
    if not config:
        return

    projects = config.get("projects")
    if not projects:
        return

    adjusted = False
    for name, proj_config in projects.items():
        if not ev.is_env_dir(proj_config["local"]):
            proj_config["status"] = _NONE_STR
            adjusted = True
        deployed_env = proj_config.get("deployed", _NONE_STR)
        if deployed_env != _NONE_STR and not ev.exists(deployed_env):
            proj_config["deployed"] = _NONE_STR
            adjusted = True

    if adjusted:
        with open(mpd_config_file(), "w") as f:
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
    if not active_env:
        return

    for name, config in projects.items():
        if active_env.path in config["local"]:
            selected_project_token().write_text(name)


def selected_project(missing_ok=True):
    token = selected_project_token()
    if token and token.exists():
        return token.read_text()

    if missing_ok:
        return None

    print()
    tty.die(f"Active MPD project required to invoke '{spack_cmd_line()}'\n")


def selected_project_config():
    return project_config(selected_project())


def print_config_info(config):
    print(f"\nUsing {cyan('build')} area: {config['build']}")
    print(f"Using {cyan('local')} area: {config['local']}")
    print(f"Using {cyan('sources')} area: {config['source']}\n")
    packages = config["packages"]
    if not packages:
        return

    print("  Will develop:")
    for p in packages:
        print(f"    - {p}")


def select(name):
    session_id = os.getsid(os.getpid())
    selected = selected_projects_dir()
    selected.mkdir(exist_ok=True)
    (selected / f"{session_id}").write_text(name)
