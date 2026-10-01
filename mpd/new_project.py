from pathlib import Path

import spack.environment as ev

from . import config
from .config import print_config_info, project_config_from_args, select, update
from .concretize import concretize_project
from .preconditions import State, preconditions
from .spack_compat import tty
from .util import bold, gray, remove_view

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
        help="directory containing repositories to develop\n(default: <top-level directory>/srcs)",
    )
    new_project.add_argument(
        "-f", "--force", action="store_true", help="replace existing project with same name and paths"
    )
    new_project.add_argument(
        "-E", "--env", help="environment (name or absolute path) from which to create project"
    )
    new_project.add_argument(
        "--require-reuse",
        action="store_true",
        help="require all dependencies to be reused from the environment specified by -E/--env",
    )
    new_project.add_argument(
        "-y", "--yes-to-all", action="store_true", help="Answer yes/default to all prompts"
    )
    new_project.add_argument(
        "-C", "--compiler", help="compiler to use (e.g., gcc@13.2.0, clang@15.0.0)"
    )
    new_project.add_argument(
        "-d",
        "--dependency",
        nargs="+",
        action="append",
        dest="dependencies",
        metavar=("SPEC", "CONSTRAINT"),
        help="specify a package with constraints (e.g., root %%gcc@11, foo ^bar@x.y.z)\n"
        "(can be specified multiple times)",
    )
    new_project.add_argument(
        "--env-var-prepend",
        action="append",
        metavar="<ENV_VAR>=<suffix>",
        help="prepend colon-separated paths to ENV_VAR for each checked-out package\n"
        "(can be specified multiple times)",
    )
    new_project.add_argument("variants", nargs="*", help="variants to apply to developed packages")


def _validate_existing_project(candidate, existing, existing_conflicts, force):
    name = candidate["name"]
    if not existing:
        return

    if not force:
        indent = " " * len("==> Error: ")
        tty.die(
            f"An MPD project with the name {bold(name)} already exists.\n"
            f"{indent}Either choose a different name or use the '--force' option"
            " to overwrite the existing project.\n"
        )

    if name in config.invalid_projects(existing_conflicts):
        tty.die(
            f"Cannot replace MPD project {bold(name)} because it has an unsafe path "
            "layout. Remove the project and recreate it instead.\n"
        )
    existing_paths = config.project_paths(existing)
    candidate_paths = config.project_paths(candidate)
    changed = [role for role in config.PATH_ROLES if existing_paths[role] != candidate_paths[role]]
    if changed:
        path_changes = "\n".join(
            f"  {role}: {existing_paths[role]} -> {candidate_paths[role]}" for role in changed
        )
        tty.die(
            f"Cannot replace MPD project {bold(name)} using different directories "
            "with '--force'.\n"
            f"The requested directories differ from those already registered:\n"
            f"{path_changes}\n"
            "'--force' replaces a project in place; it does not move its build files "
            "or Spack environment, or clean up the old directories. "
            "Changing these paths would leave stale project state behind.\n"
            f"Run 'spack mpd rm-project --force {name}' to remove the existing project, "
            "then create it again with the new paths.\n"
        )
    tty.info(f"Overwriting existing MPD project {bold(name)}")


def _validate_candidate_layout(candidate, projects, existing_conflicts):
    name = candidate["name"]
    hypothetical = dict(projects)
    hypothetical[name] = candidate
    new_conflicts = config.layout_conflicts(hypothetical)
    existing_set = set(existing_conflicts)
    introduced = [conflict for conflict in new_conflicts if conflict not in existing_set]
    candidate_conflicts = [
        conflict
        for conflict in new_conflicts
        if name in (conflict.first_project, conflict.second_project)
    ]
    if introduced or candidate_conflicts:
        tty.die(f"Cannot create MPD project '{name}'.\n{config.format_conflicts(new_conflicts)}\n")


def _validated_candidate(args):
    candidate = config.project_paths_from_args(args)
    cfg = config.mpd_config() or {"projects": {}}
    projects = cfg.get("projects") or {}
    existing = projects.get(candidate["name"])
    existing_conflicts = config.layout_conflicts(projects)

    _validate_existing_project(candidate, existing, existing_conflicts, args.force)
    _validate_candidate_layout(candidate, projects, existing_conflicts)

    return candidate, existing


def _remove_existing_environment(existing):
    local_env_dir = existing["local"]
    if ev.is_env_dir(local_env_dir):
        remove_view(local_env_dir)
        ev.Environment(local_env_dir).destroy()
        tty.info(gray(f"Removed existing environment at {local_env_dir}"))


def process(args):
    preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)

    if args.require_reuse and not args.env:
        tty.die("--require-reuse requires -E/--env.\n")

    print()

    candidate, existing = _validated_candidate(args)
    name = candidate["name"]
    if not existing:
        tty.msg(f"Creating project: {bold(name)}")

    config.prepare_project(candidate)
    project_config = project_config_from_args(args, candidate)

    if existing and args.force:
        _remove_existing_environment(existing)

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
