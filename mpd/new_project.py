from pathlib import Path

import llnl.util.tty as tty

import spack.environment as ev

from .concretize import concretize_project
from .config import mpd_project_exists, print_config_info, project_config_from_args, select, update
from .preconditions import State, preconditions
from .util import bold, gray

SUBCOMMAND = "new-project"
ALIASES = ["n"]


def setup_subparser(subparsers):
    new_project = subparsers.add_parser(
        SUBCOMMAND,
        description="create MPD development area",
        aliases=ALIASES,
        help="create MPD development area",
    )
    new_project.add_argument("--name", help="(required if --top not specified)")
    new_project.add_argument(
        "-T",
        "--top",
        default=Path.cwd(),
        help="top-level directory for MPD area\n(default: %(default)s)",
    )
    new_project.add_argument(
        "-S",
        "--srcs",
        help="directory containing repositories to develop\n"
        "(default: <top-level directory>/srcs)",
    )
    new_project.add_argument(
        "-f", "--force", action="store_true", help="overwrite existing project with same name"
    )
    new_project.add_argument(
        "-E",
        "--env",
        help="environment from which to create project\n(multiple allowed)",
    )
    new_project.add_argument(
        "-y", "--yes-to-all", action="store_true", help="Answer yes/default to all prompts"
    )
    new_project.add_argument("variants", nargs="*", help="variants to apply to developed packages")


def process(args):
    preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)

    print()

    project_config = project_config_from_args(args)
    name = project_config["name"]
    if mpd_project_exists(name):
        if args.force:
            tty.info(f"Overwriting existing MPD project {bold(name)}")
            local_env_dir = project_config["local"]
            if ev.is_env_dir(local_env_dir):
                ev.Environment(local_env_dir).destroy()
                tty.info(gray(f"Removed existing environment at {project_config['local']}"))
            Path(local_env_dir).mkdir(exist_ok=True)
        else:
            indent = " " * len("==> Error: ")
            tty.die(
                f"An MPD project with the name {bold(name)} already exists.\n"
                f"{indent}Either choose a different name or use the '--force' option"
                " to overwrite the existing project.\n"
            )
    else:
        tty.msg(f"Creating project: {bold(name)}")

    print_config_info(project_config)
    select(name)

    if len(project_config["packages"]):
        concretize_project(project_config, args.yes_to_all)
    else:
        update(project_config, status="ready")
        tty.msg(
            "You can clone repositories for development by invoking\n\n"
            f"  {gray('>')} spack mpd git-clone --suites <suite name>\n\n"
            "  (or type 'spack mpd git-clone --help' for more options)\n"
        )
