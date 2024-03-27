import re
from pathlib import Path

import ruamel

import llnl.util.tty as tty

import spack.util.spack_yaml as syaml


def mpd_local_dir():
    return Path.home() / ".mpd"


def mpd_packages():
    return mpd_local_dir() / "packages"


def mpd_config_file():
    return mpd_local_dir() / "config"


def _compiler(variants):
    compiler = None
    compiler_index = None
    for i, variant in enumerate(variants):
        match = re.fullmatch(r"%(\w+@[\d\.]+)", variant)
        if match:
            compiler = match[1]
            compiler_index = i
            break
    return compiler, compiler_index


def _cxxstd(variants):
    cxx_standard = "17"  # Must be a string for CMake
    cxxstd_index = None
    for i, variant in enumerate(variants):
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

    project["cxxstd"] = cxxstd
    project["variants"] = " ".join(args.variants)
    return project


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


def update_mpd_config(project_config, installed):
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
    yaml_project_config.update(installed=installed)
    config["projects"][project_config["name"]] = yaml_project_config

    # Update .mpd file
    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)


def refresh_mpd_config(project_name):
    config_file = mpd_config_file()
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    # Update packages field
    assert config is not None
    assert project_name is not None
    config = project_config(project_name, config)
    sp = Path(config["source"])
    assert sp.exists()
    packages_to_develop = sorted(
        f.name for f in sp.iterdir() if not f.name.startswith(".") and f.is_dir()
    )

    # Update .mpd file
    config["projects"][project_name]["packages"] = packages_to_develop
    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)

    # Return configuration for this project
    return config["projects"][project_name]


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
