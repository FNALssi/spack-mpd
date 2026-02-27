import subprocess
from pathlib import Path

import spack.llnl.util.tty as tty

from .config import selected_project_config
from .preconditions import State, activate_development_environment, preconditions
from .util import cyan, remove_dir

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
        "--configure-only", action="store_true", help="run CMake configuration only, do not build"
    )
    build.add_argument(
        "-j",
        dest="parallel",
        metavar="<number>",
        help="specify number of threads for parallel build",
    )
    build.add_argument(
        "-D",
        "--define-variable",
        dest="cmake_defines",
        action="append",
        help="CMake variable definition (e.g. -DFOO:STRING=bar)",
        metavar="<var>:<type>=<value>",
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


def configure_cmake_project(project_config, cmake_defines=None):
    configure_list = [
        "cmake",
        "--preset",
        "default",
        project_config["source"],
        "-B",
        project_config["build"],
        "-G",
        _generator_value(project_config),
    ]

    if cmake_defines:
        configure_list.extend([f"-D{define}" for define in cmake_defines])

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


def configure(project_config, cmake_defines=None):
    result = configure_cmake_project(project_config, cmake_defines)
    if result.returncode != 0:
        print()
        tty.die("The CMake configure step failed. See above\n")


def build(project_config, parallel, generator_options):
    build_area = project_config["build"]
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
        remove_dir(Path(config["build"]))

    activate_development_environment(config["local"])

    build_area = config["build"]
    if not (Path(build_area) / "CMakeCache.txt").exists():
        configure(config, args.cmake_defines)

    if not args.configure_only:
        build(config, args.parallel, args.generator_options)
