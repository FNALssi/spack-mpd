import re
from pathlib import Path

import ruamel

import llnl.util.tty as tty

import spack.util.spack_yaml as syaml


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


def update_mrb_config(project_name, top_dir, srcs_dir, variants, overwrite_allowed=False):
    mrb_config_file = Path.home() / ".mrb"
    mrb_config = None
    if mrb_config_file.exists():
        with open(mrb_config_file, "r") as f:
            mrb_config = syaml.load(f)

    if mrb_config is None:
        mrb_config = ruamel.yaml.comments.CommentedMap()
        mrb_config["projects"] = ruamel.yaml.comments.CommentedMap()

    projects = mrb_config.get("projects")
    boldname = tty.color.colorize("@*{" + project_name + "}")
    if project_name in projects:
        print()
        if overwrite_allowed:
            tty.warn(f"Overwriting existing MRB project {boldname}\n")
        else:
            indent = " " * len("==> Error: ")
            tty.die(
                f"An MRB project with the name {boldname} already exists.\n"
                + f"{indent}Either choose a different name or use the '--force' option to overwrite the existing project.\n"
            )

    # Can update
    project = ruamel.yaml.comments.CommentedMap()
    project["top"] = str(top_dir)
    project["source"] = str(srcs_dir)
    project["build"] = str((top_dir / "build").absolute())
    project["local"] = str((top_dir / "local").absolute())
    project["install"] = str((top_dir / "local" / "install").absolute())
    project["local_spack_packages"] = str((top_dir / "local" / "packages").absolute())
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
    project["variants"] = ruamel.yaml.scalarstring.SingleQuotedScalarString(" ".join(variants))
    mrb_config["projects"][project_name] = project

    # Update .mrb file
    with open(mrb_config_file, "w") as f:
        syaml.dump(mrb_config, stream=f)

    # Return configuration for this project
    return project


def project_config(name):
    mrb_config_file = Path.home() / ".mrb"
    mrb_config = None
    if mrb_config_file.exists():
        with open(mrb_config_file, "r") as f:
            mrb_config = syaml.load(f)

    if mrb_config is None:
        print()
        tty.die("Missing MRB configuration.  Please contact scisoft-team@fnal.gov\n")

    projects = mrb_config.get("projects")
    if name not in projects:
        print()
        tty.die(
            f"Project '{name}' not supported by MRB configuration.  Please contact scisoft-team@fnal.gov\n"
        )

    return projects[name]
