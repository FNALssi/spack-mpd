import os

description = "create multi-repository build area"
section = "scripting"
level = "long"

from ..build import build
from ..clean import clean
from ..new_dev import new_dev
from .. import clone


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
    build.add_argument(
        "--clean", action="store_true", help="clean build area before building"
    )
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

    git = subparsers.add_parser(
        "git-clone",
        description="clone git repositories for development",
        aliases=["g", "gitCheckout"],
        help="clone git repositories",
    )
    git.add_argument("--suite")
    git.add_argument("--help-repos", action="store_true", help="list supported repositories")
    git.add_argument("--help-suites", action="store_true", help="list supported suites")

    install = subparsers.add_parser(
        "install",
        description="install (and build if necessary) repositories",
        aliases=["i"],
        help="install built repositories",
    )
    newDev = subparsers.add_parser(
        "new-dev",
        description="create new development area",
        aliases=["n", "newDev"],
        help="create new development area",
    )
    newDev.add_argument("--name", required=True)
    newDev.add_argument("--top", required=True)
    newDev.add_argument("-D", "--dir", required=True)
    newDev.add_argument("variants", nargs="*")

    test = subparsers.add_parser(
        "test",
        description="build and run tests",
        aliases=["t"],
        help="build and run tests",
    )
    zap = subparsers.add_parser(
        "zap-build",
        description="delete everything in your build area",
        aliases=["z", "zapBuild"],
        help="delete everything in your build area",
    )


def mrb(parser, args):
    if args.mrb_subcommand in ("new-dev", "n", "newDev"):
        new_dev(args.name, args.top, args.dir, args.variants)
        return
    if args.mrb_subcommand in ("git-clone", "g", "gitCheckout"):
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
            srcs,
            build_area,
            install_area,
            args.generator,
            args.parallel,
            args.generator_options,
        )
        return
    if args.mrb_subcommand in ("zap-build", "z"):
        clean(os.environ["MRB_BUILDDIR"])
        return
