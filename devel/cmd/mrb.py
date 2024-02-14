import os
import sys
from pathlib import Path

import llnl.util.tty as tty

description = "create multi-repository build area"
section = "scripting"
level = "long"

from .. import clone
from ..build import build
from ..clean import clean
from ..list_projects import list_projects, project_details, project_path
from ..mrb_config import project_config, refresh_mrb_config, update_mrb_config
from ..new_project import new_project


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
    git_parser.add_argument(
        "repos",
        metavar="<repo spec>",
        nargs="*",
        help="a specification of a repository to clone. The repo spec may either be:\n"
        + "(a) any repository name listed by the --help-repos option, or\n"
        + "(b) any URL to a Git repository.",
    )
    git = git_parser.add_mutually_exclusive_group()
    git.add_argument("--help-repos", action="store_true", help="list supported repositories")
    git.add_argument("--help-suites", action="store_true", help="list supported suites")
    git.add_argument(
        "--suite",
        metavar="<suite name>",
        help="clone repositories corresponding to the given suite name",
    )

    install = subparsers.add_parser(
        "install",
        description="install (and build if necessary) repositories",
        aliases=["i"],
        help="install built repositories",
    )

    lst_description = (
        "list MRB projects\n\n"
        + "When no arguments are specified, prints a list of known MRB projects\n"
        + "and their corresponding top-level directories."
    )
    lst = subparsers.add_parser(
        "list", description=lst_description, aliases=["ls"], help="list MRB projects"
    )
    lst.add_argument(
        "project", metavar="<project name>", nargs="*", help="print details of the MRB project"
    )
    lst.add_argument(
        "-t", "--top", metavar="<project name>", help="print top-level directory for project"
    )

    default_top = Path.cwd()
    new_project_description = f"create new development area\n\nIf the '--top' option is not specified, the current working directory will be used:\n  {default_top}"
    newDev = subparsers.add_parser(
        "new-project",
        description=new_project_description,
        aliases=["n", "newDev"],
        help="create new development area",
    )
    newDev.add_argument("--name", required=True)
    newDev.add_argument(
        "--top", metavar="<dir>", default=default_top, help="top-level directory for MRSB area"
    )
    newDev.add_argument("-D", "--dir", help="directory containing repositories to develop")
    newDev.add_argument(
        "-f", "--force", action="store_true", help="overwrite existing project with same name"
    )
    newDev.add_argument("variants", nargs="*")

    refresh = subparsers.add_parser(
        "refresh", description="refresh project area", help="refresh project area"
    )

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


def _active_project():
    name = os.environ.get("MRB_PROJECT")
    if name is None:
        print()
        tty.die(f"Active MRB project required to invoke 'spack {' '.join(sys.argv[1:])}'\n")
    return name


def _active_project_config():
    return project_config(_active_project())


def mrb(parser, args):
    if args.mrb_subcommand in ("new-project", "n", "newDev"):
        config = update_mrb_config(
            args.name,
            Path(args.top).absolute(),
            Path(args.dir).absolute(),
            args.variants,
            args.force,
        )
        new_project(args.name, config)
        return
    if args.mrb_subcommand in ("list", "ls"):
        if args.project:
            project_details(args.project)
        elif args.top:
            project_path(args.top, "top")
        else:
            list_projects()
        return
    if args.mrb_subcommand in ("git-clone", "g", "gitCheckout"):
        if args.repos:
            config = _active_project_config()
            clone.clone_repos(args.repos, config["source"], config["local"])
        else:
            if args.suite:
                config = _active_project_config()
                clone.clone_suite(args.suite, config["source"], config["local"])
            elif args.help_suites:
                clone.help_suites()
            elif args.help_repos:
                clone.help_repos()
            else:
                print()
                tty.die(
                    f"At least one option required when invoking 'spack {' '.join(sys.argv[1:])}'\n"
                )
        return
    if args.mrb_subcommand in ("build", "b"):
        config = _active_project_config()
        srcs, build_area, install_area = (config["source"], config["build"], config["install"])
        if args.clean:
            clean(build_area)

        build(
            srcs, build_area, install_area, args.generator, args.parallel, args.generator_options
        )
        return

    if args.mrb_subcommand in ("zap", "z"):
        config = _active_project_config()
        if args.zap_install:
            clean(config["install"])
        if args.zap_all:
            clean(config["install"])
            clean(config["build"])
        if args.zap_build:
            clean(config["build"])
        return

    if args.mrb_subcommand == "refresh":
        name = _active_project()
        current_config = project_config(name)
        new_config = refresh_mrb_config(name)
        if current_config == new_config:
            tty.msg(f"Project {name} is up-to-date")
            return
        update_project(name, new_config)
