import shutil
from pathlib import Path

import llnl.util.filesystem as fs
import llnl.util.tty as tty

import spack.config
import spack.paths

from . import config

SUBCOMMAND = "init"

MPD_DIR = Path(spack.paths.prefix) / "var" / "mpd"


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


def initialized():
    return config.mpd_config_dir().exists()


def process(args):
    spack_root = spack.paths.prefix

    local_dir = MPD_DIR.resolve()
    spack.config.set("config:mpd_dir", str(local_dir))

    if initialized() and not args.force:
        assert local_dir.exists()
        tty.warn(f"MPD already initialized for Spack instance at {spack_root}")
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

        shutil.rmtree(local_dir, ignore_errors=True)

    tty.msg(f"Using Spack instance at {spack_root}")

    config.selected_projects_dir().mkdir(exist_ok=True)
