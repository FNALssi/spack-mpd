import shutil
from pathlib import Path

import spack.config
import spack.llnl.util.filesystem as fs
import spack.llnl.util.tty as tty
import spack.paths

from .util import gray

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


def mpd_config_dir():
    return Path(spack.config.get("config:mpd_dir", MPD_DIR.resolve(), scope="site"))


def mpd_config_file(config_dir):
    return config_dir / "config"


def mpd_selected_projects_dir(config_dir):
    return config_dir / "selected"


def initialized():
    config_dir = mpd_config_dir()
    config_file = mpd_config_file(mpd_config_dir())
    selected_projects_dir = mpd_selected_projects_dir(mpd_config_dir())
    return config_dir.exists() and config_file.exists() and selected_projects_dir.exists()


def initialize_mpd(config_dir):
    config_dir.mkdir(exist_ok=True)
    mpd_config_file(config_dir).touch(exist_ok=True)
    mpd_selected_projects_dir(config_dir).mkdir(exist_ok=True)


def process(args):
    spack_root = spack.paths.prefix

    config_dir = mpd_config_dir()
    if initialized() and not args.force:
        tty.warn(f"MPD already initialized for Spack instance at {spack_root}")
        tty.msg(gray(f"MPD configuration directory: {config_dir}"))
        return

    if not fs.can_access(spack_root):
        indent = " " * len("==> Error: ")
        tty.die(
            "To use MPD, you must have a Spack instance you can write to.\n"
            f"{indent}You do not have permission to write to the Spack instance above.\n"
            f"{indent}Please contact scisoft-team@fnal.gov for guidance."
        )

    # If the value of "config:mpd_dir" has not been set yet, we set it here.  If
    # it has already been set, we are simply setting it to its current value.
    # The default returned by mpd_config_dir() is the value of MPD_DIR.
    spack.config.set("config:mpd_dir", str(config_dir), scope="site")

    if config_dir.exists() and args.force:
        tty.warn("Reinitializing MPD on this system will remove all MPD projects")
        if args.yes:
            should_reinitialize = True
        else:
            should_reinitialize = tty.get_yes_or_no(
                "Would you like to proceed with reinitialization?", default=False
            )
        if not should_reinitialize:
            tty.info("No changes made")
            return

        shutil.rmtree(config_dir, ignore_errors=True)

    tty.msg(f"MPD initialized for Spack instance at {spack_root}")
    tty.msg(gray(f"MPD configuration directory: {config_dir}"))
    initialize_mpd(config_dir)
