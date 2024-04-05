import subprocess

import llnl.util.filesystem as fs

from .config import selected_project_config
from .preconditions import preconditions, State

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


def build(srcs, build_area, install_area, generator, parallel, generator_options):
    configure_list = [
        "cmake",
        "--preset",
        "default",
        srcs,
        "-B",
        build_area,
        f"-DCMAKE_INSTALL_PREFIX={install_area}",
    ]
    if generator:
        configure_list += ["-G", generator]
    subprocess.run(configure_list)

    generator_list = ["--"]
    if parallel:
        generator_list.append(f"-j{parallel}")
    if generator_options:
        generator_list += generator_options

    subprocess.run(["cmake", "--build", build_area] + generator_list)


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, State.ACTIVE_ENVIRONMENT)

    config = selected_project_config()
    srcs, build_area, install_area = (config["source"], config["build"], config["install"])
    if args.clean:
        fs.remove_directory_contents(build_area)

    build(srcs, build_area, install_area, args.generator, args.parallel, args.generator_options)
