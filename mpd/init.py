import shutil
from collections import namedtuple

import llnl.util.filesystem as fs
import llnl.util.tty as tty

import spack.cmd.repo
import spack.config
import spack.paths
import spack.repo

from pathlib import Path
from . import config


SUBCOMMAND = "init"


def setup_subparser(subparsers):
    init = subparsers.add_parser(
        SUBCOMMAND,
        description="initialize MPD on this system",
        help="initialize MPD on this system",
    )
    init.add_argument("-f", "--force", action="store_true", help="allow reinitialization")
    init.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help='assume "yes" is the answer to confirmation request for reinitialization',
    )
    init.add_argument("-u", "--user-dir", 
                      action="store", 
                      help="Set MPD configuration directory (default ~/.mpd)",
                      default=(Path.home() / ".mpd").resolve())
    init.add_argument("-r", "--repo-scope", action="store", help="Set Spack configuration scope to use (default: user)", default="user")


def initialized():
    local_dir = config.user_config_dir()
    repos = spack.config.get("repos")
    tty.debug(f"Checking that local user dir {str(local_dir)} exists and that it is in the list {repos}")
    return local_dir.exists() and str(local_dir) in repos #, scope="user"


def process(args):
    spack_root = spack.paths.prefix

    if args.user_dir is not None:
        local_dir = Path(args.user_dir).resolve()
        spack.config.set('config:mpd_user_dir', str(local_dir))
    else:
        local_dir = config.user_config_dir()

    if initialized() and not args.force:
        assert local_dir.exists()
        tty.msg(f"Using Spack instance at {spack_root}")
        tty.warn(f"MPD already initialized on this system ({local_dir})")
        return

    if not fs.can_access(spack_root):
        indent = " " * len("==> Error: ")
        print()
        tty.die(
            "To use MPD, you must have a Spack instance you can write to.\n"
            + indent
            + "You do not have permission to write to the Spack instance above.\n"
            + indent
            + "Please contact scisoft-team@fnal.gov for guidance."
        )

    if local_dir.exists() and args.force:
        tty.warn("Reinitializing MPD on this system will remove all MPD projects")
        if args.yes:
            should_reinitialize = True
        else:
            should_reinitialize = tty.get_yes_or_no(
                "Would you like to proceed with reinitialization?", default=False
            )
        if not should_reinitialize:
            return tty.info("No changes made")

        if str(local_dir) in spack.config.get("repos"): 
            RemoveArgs = namedtuple("args", ["namespace_or_path", "scope"])
            spack.cmd.repo.repo_remove(RemoveArgs(namespace_or_path=str(local_dir), scope=args.repo_scope))
        shutil.rmtree(local_dir, ignore_errors=True)

    full_path, _ = spack.repo.create_repo(
        str(local_dir), "local-mpd", spack.repo.packages_dir_name
    )
    tty.msg(f"Using Spack instance at {spack_root}")

    # The on-disk configuration is adjusted in this process, so we must clear the caches
    # to force repo_add to reread the configuration files.
    spack.config.CONFIG.clear_caches()
    AddArgs = namedtuple("args", ["path", "scope"])
    spack.cmd.repo.repo_add(AddArgs(path=full_path, scope=args.repo_scope))

    config.selected_projects_dir().mkdir(exist_ok=True)
