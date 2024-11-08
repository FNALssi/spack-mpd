import subprocess

import llnl.util.filesystem as fs
import llnl.util.tty as tty

import spack

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


def build(project_config, generator, parallel, generator_options):
    build_area = project_config["build"]
    compilers = spack.compilers.compilers_for_spec(project_config["compiler"])
    assert len(compilers) == 1
    configure_list = [
        "cmake",
        "--preset",
        "default",
        project_config["source"],
        "-B",
        build_area,
        f"-DCMAKE_C_COMPILER={compilers[0].cc}",
        f"-DCMAKE_CXX_COMPILER={compilers[0].cxx}",
    ]
    if generator:
        configure_list += ["-G", generator]

    configure_list_str = " ".join(configure_list)
    print()
    tty.msg("Configuring with command:\n\n" + cyan(configure_list_str) + "\n")

    subprocess.run(configure_list)

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
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, State.ACTIVE_ENVIRONMENT)

    config = selected_project_config()
    if args.clean:
        fs.remove_directory_contents(config["build"])

    build(config, args.generator, args.parallel, args.generator_options)
