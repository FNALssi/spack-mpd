import re
import subprocess
from pathlib import Path

import ruamel

import llnl.util.tty as tty

import spack.util.spack_yaml as syaml

from .util import bold


def mrb_local_dir():
    return Path.home() / ".mrb"


def mrb_config_file():
    return mrb_local_dir() / "config"


def _compiler(variants):
    compiler = None
    compiler_index = None
    for i, variant in enumerate(variants):
        match = re.fullmatch("%(\w+@[\d\.]+)", variant)
        if match:
            compiler = match[1]
            compiler_index = i
    return compiler, compiler_index


def _cxxstd(variants):
    cxx_standard = "17"  # Must be a string for CMake
    cxxstd_index = None
    for i, variant in enumerate(variants):
        match = re.fullmatch("cxxstd=(\d{2})", variant)
        if match:
            cxx_standard = match[1]
            cxxstd_index = i
    return cxx_standard, cxxstd_index


def update_mrb_config(
    project_name, top_dir, srcs_dir, variants, overwrite_allowed=False, update_file=False
):
    config_file = mrb_config_file()
    config = None
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    if config is None:
        config = ruamel.yaml.comments.CommentedMap()
        config["projects"] = ruamel.yaml.comments.CommentedMap()

    projects = config.get("projects")
    if project_name in projects:
        print()
        if overwrite_allowed:
            tty.warn(
                f"Installing {bold(project_name)} again will overwriting existing MRB project"
            )
        else:
            indent = " " * len("==> Error: ")
            tty.die(
                f"An MRB project with the name {bold(project_name)} already exists.\n"
                + f"{indent}Either choose a different name or use the '--force' option to overwrite the existing project.\n"
            )
    else:
        # Check if package already exists
        result = subprocess.run(
            ["spack", "find", project_name], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL
        )
        if result.returncode == 0:
            tty.die(f"A package with the name {bold(project_name)} already exists.")

    # Can update
    project = ruamel.yaml.comments.CommentedMap()
    project["top"] = str(top_dir)
    project["source"] = str(srcs_dir)
    project["build"] = str((top_dir / "build").absolute())
    project["local"] = str((top_dir / "local").absolute())
    project["install"] = str((top_dir / "local" / "install").absolute())

    sp = Path(srcs_dir)
    packages_to_develop = []
    if sp.exists():
        packages_to_develop = sorted(
            f.name for f in sp.iterdir() if not f.name.startswith(".") and f.is_dir()
        )
    project["packages"] = packages_to_develop

    # Select and remove compiler
    compiler, compiler_index = _compiler(variants)
    if compiler_index is not None:
        del variants[compiler_index]

    # Select and remove cxxstd
    cxxstd, cxxstd_index = _cxxstd(variants)
    if cxxstd_index is not None:
        del variants[cxxstd_index]

    if compiler:
        project["compiler"] = compiler

    project["cxxstd"] = cxxstd
    project["variants"] = " ".join(variants)
    config["projects"][project_name] = project

    # Update .mrb file
    if update_file:
        with open(config_file, "w") as f:
            syaml.dump(config, stream=f)

    # Return configuration for this project
    return project


def refresh_mrb_config(project_name):
    config_file = mrb_config_file()
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

    # Update .mrb file
    config["projects"][project_name]["packages"] = packages_to_develop
    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)

    # Return configuration for this project
    return config["projects"][project_name]


def rm_config(project_name):
    config_file = mrb_config_file()
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
        config_file = mrb_config_file()
        if config_file.exists():
            with open(config_file, "r") as f:
                config = syaml.load(f)

    if config is None:
        print()
        tty.die("Missing MRB configuration.  Please contact scisoft-team@fnal.gov\n")

    projects = config.get("projects")
    if name not in projects:
        print()
        tty.die(
            f"Project '{name}' not supported by MRB configuration.  Please contact scisoft-team@fnal.gov\n"
        )

    return projects[name]
