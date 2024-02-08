import os
from pathlib import Path

description = "create multi-repository build area"
section = "scripting"
level = "long"

from .. import clone
from ..build import build
from ..clean import clean
from ..new_dev import new_dev


def setup_parser(subparser):
    subparsers = subparser.add_subparsers(dest="mrb_subcommand")
    build = subparsers.add_parser(
        "build",
        description="build repositories under development",
        aliases=["b"],
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

    git_parser = subparsers.add_parser(
        "git-clone",
        description="clone git repositories for development",
        aliases=["g", "gitCheckout"],
        help="clone git repositories",
    )
    git = git_parser.add_mutually_exclusive_group(required=True)
    git.add_argument("--help-repos", action="store_true", help="list supported repositories")
    git.add_argument("--help-suites", action="store_true", help="list supported suites")
    git.add_argument(
        "--suite",
        metavar="<suite name>",
        help="install repositories corresponding to the given suite name",
    )

    install = subparsers.add_parser(
        "install",
        description="install (and build if necessary) repositories",
        aliases=["i"],
        help="install built repositories",
    )

    default_top = Path.cwd()
    new_dev_description = f"create new development area\n\nIf the '--top' option is not specified, the current working directory will be used:\n  {default_top}"
    newDev = subparsers.add_parser(
        "new-dev",
        description=new_dev_description,
        aliases=["n", "newDev"],
        help="create new development area",
    )
    newDev.add_argument("--name", required=True)
    newDev.add_argument(
        "--top", metavar="<dir>", default=default_top, help="Top-level directory for MRSB area"
    )
    newDev.add_argument("-D", "--dir", help="Directory containing repositories to develop")
    newDev.add_argument("variants", nargs="*")

    test = subparsers.add_parser(
        "test", description="build and run tests", aliases=["t"], help="build and run tests"
    )
    zap_parser = subparsers.add_parser(
        "zap",
        description="delete everything in your build and/or install areas.\n\nIf no optional argument is provided, the '--build' option is assumed.",
        aliases=["z"],
        help="delete everything in your build and/or install areas",
    )
    zap = zap_parser.add_mutually_exclusive_group()
    zap.add_argument(
        "--all",
        dest="zap_all",
        action="store_true",
        help="delete everything in your build and install directories",
    )
    zap.add_argument(
        "--build",
        dest="zap_build",
        action="store_true",
        default=True,
        help="delete everything in your build directory",
    )
    zap.add_argument(
        "--install",
        dest="zap_install",
        action="store_true",
        help="delete everything in your install directory",
    )


def mrb(parser, args):
    if args.mrb_subcommand in ("new-dev", "n", "newDev"):
        new_dev(args.name, args.top, args.dir, args.variants)
        return
    if args.mrb_subcommand in ("git-clone", "g", "gitCheckout"):
        if args.suite:
            clone.clone_suite(args.suite, os.environ["MRB_SOURCE"], os.environ["MRB_LOCAL"])
        if args.help_suites:
            clone.help_suites()
        if args.help_repos:
            clone.help_repos()
        return
    if args.mrb_subcommand in ("build", "b"):
        srcs, build_area, install_area = (
            os.environ["MRB_SOURCE"],
            os.environ["MRB_BUILDDIR"],
            os.environ["MRB_INSTALL"],
        )
        if args.clean:
            clean(build_area)

        build(
            srcs, build_area, install_area, args.generator, args.parallel, args.generator_options
        )
        return
    if args.mrb_subcommand in ("zap", "z"):
        if args.zap_install:
            clean(os.environ["MRB_INSTALL"])
        if args.zap_all:
            clean(os.environ["MRB_INSTALL"])
            clean(os.environ["MRB_BUILDDIR"])
        if args.zap_build:
            clean(os.environ["MRB_BUILDDIR"])
        return
