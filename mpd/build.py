import subprocess
from pathlib import Path

import llnl.util.filesystem as fs
import llnl.util.tty as tty

import spack
import spack.environment as ev
import spack.environment.shell as ev_shell

from .config import selected_project_config
from .preconditions import State, preconditions
from .util import cyan

SUBCOMMAND = "build"
ALIASES = ["b"]


def setup_subparser(subparsers):
    build = subparsers.add_parser(
        SUBCOMMAND,
        description="build repositories under development",
        aliases=ALIASES,
        help="build repositories",
    )
    build.add_argument(
        "--generator",
        "-G",
        metavar="<generator name>",
        help="generator used to build CMake project",
    )
    build.add_argument("--clean", action="store_true", help="clean build area before building")
    build.add_argument(
        "-j",
        dest="parallel",
        metavar="<number>",
        help="specify number of threads for parallel build",
    )
    build.add_argument(
        "generator_options",
        metavar="-- <generator options>",
        nargs="*",
        help="options passed directly to generator",
    )


def configure_cmake_project(project_config, compilers, generator):
    configure_list = [
        "cmake",
        "--preset",
        "default",
        project_config["source"],
        "-B",
        project_config["build"],
        f"-DCMAKE_C_COMPILER={compilers[0].cc}",
        f"-DCMAKE_CXX_COMPILER={compilers[0].cxx}",
    ]
    if generator:
        configure_list += ["-G", generator]

    configure_list_str = " ".join(configure_list)
    print()
    tty.msg("Configuring with command:\n\n" + cyan(configure_list_str) + "\n")

    subprocess.run(configure_list)


def build(project_config, generator, parallel, generator_options):
    build_area = project_config["build"]
    compilers = spack.compilers.compilers_for_spec(project_config["compiler"])
    assert len(compilers) == 1

    if not (Path(build_area) / "CMakeCache.txt").exists():
        configure_cmake_project(project_config, compilers, generator)

    generator_list = []
    if parallel:
        generator_list.append(f"-j{parallel}")
    if generator_options:
        generator_list += generator_options

    if generator_list:
        generator_list.insert(0, "--")

    all_arguments = ["cmake", "--build", build_area] + generator_list
    all_arguments_str = " ".join(all_arguments)
    print()
    tty.msg("Building with command:\n\n" + cyan(all_arguments_str) + "\n")

    subprocess.run(all_arguments)


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT)

    config = selected_project_config()
    if args.clean:
        fs.remove_directory_contents(config["build"])

    development_env = ev.Environment(config["local"])
    ev_shell.activate(development_env).apply_modifications()
    build(config, args.generator, args.parallel, args.generator_options)
