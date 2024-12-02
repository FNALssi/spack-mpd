import subprocess
from pathlib import Path

import llnl.util.filesystem as fs
import llnl.util.tty as tty

import spack
import spack.compilers

from .config import selected_project_config
from .preconditions import State, activate_development_environment, preconditions
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


def _generator_value(project_config):
    value = project_config["generator"]["value"]
    if value == "make":
        return "Unix Makefiles"
    if value == "ninja":
        return "Ninja"
    tty.die(f"Only 'make' and 'ninja' generators are allowed (specified {value}).")


def configure_cmake_project(project_config, compilers):
    configure_list = [
        "cmake",
        "--preset",
        "default",
        project_config["source"],
        "-B",
        project_config["build"],
        "-G",
        _generator_value(project_config)
    ]
    if compilers:
        configure_list += [
            f"-DCMAKE_C_COMPILER={compilers[0].cc}",
            f"-DCMAKE_CXX_COMPILER={compilers[0].cxx}",
        ]

    printed_configure_list = []
    for arg in configure_list:
        if arg.count(" ") > 0:
            printed_configure_list.append(f'"{arg}"')
        else:
            printed_configure_list.append(arg)

    configure_list_str = " ".join(printed_configure_list)
    print()
    tty.msg("Configuring with command:\n\n" + cyan(configure_list_str) + "\n")

    return subprocess.run(configure_list)


def build(project_config, parallel, generator_options):
    build_area = project_config["build"]
    desired_compiler = project_config["compiler"]["value"]
    compilers = []
    if desired_compiler:
        compilers = spack.compilers.compilers_for_spec(desired_compiler)
        assert len(compilers) == 1

    if not (Path(build_area) / "CMakeCache.txt").exists():
        result = configure_cmake_project(project_config, compilers)
        if result.returncode != 0:
            print()
            tty.die("The CMake configure step failed. See above\n")

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
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, State.PACKAGES_TO_DEVELOP)

    config = selected_project_config()
    if args.clean:
        fs.remove_directory_contents(config["build"])

    activate_development_environment(config["local"])
    build(config, args.parallel, args.generator_options)
