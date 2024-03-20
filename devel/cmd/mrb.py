import os
import sys
from pathlib import Path

import llnl.util.tty as tty

description = "create multi-repository build area"
section = "scripting"
level = "long"

from .. import clone
from ..build import build
from ..init import init
from ..list_projects import list_projects, project_details, project_path
from ..mrb_config import project_config, refresh_mrb_config, update_mrb_config
from ..new_project import make_setup_file, new_project, update_project
from ..rm_project import rm_project
from ..util import bold, clean


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

    init = subparsers.add_parser(
        "init", description="initialize MRB on this system", help="initialize MRB on this system"
    )

    install = subparsers.add_parser(
        "install",
        description="install (and build if necessary) repositories",
        aliases=["i"],
        help="install built repositories",
    )

    lst_description = """list MRB projects

When no arguments are specified, prints a list of known MRB projects
and their corresponding top-level directories."""
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
    new_project_description = f"""create new development area

If the '--top' option is not specified, the current working directory will be used:
  {default_top}"""
    new_project = subparsers.add_parser(
        "new-project",
        description=new_project_description,
        aliases=["n", "newDev"],
        help="create new development area",
    )
    new_project.add_argument("--name", required=True)
    new_project.add_argument(
        "-T",
        "--top",
        metavar="<dir>",
        default=default_top,
        help="top-level directory for MRSB area",
    )
    new_project.add_argument(
        "-S", "--srcs", metavar="<dir>", help="directory containing repositories to develop"
    )
    new_project.add_argument(
        "-f", "--force", action="store_true", help="overwrite existing project with same name"
    )
    new_project.add_argument(
        "-E", "--from-env", metavar="<env>", help="environment from which to create project"
    )
    new_project.add_argument("variants", nargs="*")

    refresh = subparsers.add_parser(
        "refresh", description="refresh project area", help="refresh project area"
    )

    rm_proj_description = """remove MRB project

Removing a project will:

  * Remove the project entry from the list printed by 'spack mrb list'
  * Delete the 'build' and 'local' directories
  * If '--full' specified, delete the entire 'top' level directory tree of the
    project (including the specified sources directory if it resides
    within the top-level directory).
  * Uninstall the project's package/environment"""
    rm_proj = subparsers.add_parser(
        "rm-project", description=rm_proj_description, aliases=["rm"], help="remove MRB project"
    )
    rm_proj.add_argument("project", metavar="<project name>", help="MRB project to remove")
    rm_proj.add_argument(
        "--full",
        action="store_true",
        help="remove entire directory tree starting at the top level of the project",
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
    if args.mrb_subcommand in ("build", "b"):
        config = _active_project_config()
        srcs, build_area, install_area = (config["source"], config["build"], config["install"])
        if args.clean:
            clean(build_area)

        build(
            srcs, build_area, install_area, args.generator, args.parallel, args.generator_options
        )
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

    if args.mrb_subcommand == "init":
        init()
        return

    if args.mrb_subcommand in ("list", "ls"):
        if args.project:
            project_details(args.project)
        elif args.top:
            project_path(args.top, "top")
        else:
            list_projects()
        return

    if args.mrb_subcommand in ("new-project", "n", "newDev"):
        top_path = Path(args.top)
        srcs_path = Path(args.srcs) if args.srcs else top_path / "srcs"
        config = update_mrb_config(
            args.name, top_path.absolute(), srcs_path.absolute(), args.variants, args.force
        )
        new_project(args.name, args.from_env, config)
        return

    if args.mrb_subcommand == "refresh":
        name = _active_project()
        current_config = project_config(name)
        new_config = refresh_mrb_config(name)
        if current_config == new_config:
            tty.msg(f"Project {name} is up-to-date")
            return
        update_project(name, new_config)
        return

    if args.mrb_subcommand in ("rm-project", "rm"):
        config = project_config(args.project)
        if args.project == os.environ.get("MRB_PROJECT"):
            print()
            tty.die(
                f"Cannot remove active MRB project {bold(args.project)}.  Deactivate by invoking:\n\n"
                + f"           spack unload {args.project}\n"
            )
        rm_project(args.project, config, args.full)
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


# The following is invoked post-installation
def add_project(name, top_dir, srcs_dir, variants):
    config = update_mrb_config(
        name,
        Path(top_dir),
        Path(srcs_dir),
        variants.split(),
        overwrite_allowed=True,
        update_file=True,
    )
    make_setup_file(name, config["compiler"], config)
    tty.msg(bold("To setup your user environment, invoke") + f"\n\n  source {srcs_dir}/setup.sh\n")
