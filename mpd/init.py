import errno
import tempfile
from collections import namedtuple

import llnl.util.tty as tty

import spack.cmd.repo
import spack.config
import spack.paths
import spack.repo

from . import config

# FIXME: Probably need ability to reinit.


def setup_subparser(subparsers):
    subparsers.add_parser(
        "init", description="initialize MPD on this system", help="initialize MPD on this system"
    )


# Inspired by/pilfered from https://stackoverflow.com/a/25868839/3585575
def _is_writeable(path):
    try:
        testfile = tempfile.TemporaryFile(dir=path)
        testfile.close()
    except OSError as e:
        if e.errno in (errno.EACCES, errno.EEXIST):  # 13, # 17
            return False
        e.filename = path
        raise
    return True


def initialized():
    local_dir = config.user_config_dir()
    return local_dir.exists() and str(local_dir) in spack.config.get("repos", scope="user")


def process(args):
    spack_root = spack.paths.prefix
    tty.msg(f"Using Spack instance at {spack_root}")
    local_dir = config.user_config_dir()
    if initialized():
        assert local_dir.exists()
        tty.warn(f"MPD already initialized on this system ({local_dir})")
        return

    if not _is_writeable(spack_root):
        indent = " " * len("==> Error: ")
        print()
        tty.die(
            "To use MPD, you must have a Spack instance you can write to.\n"
            + indent
            + "You do not have permission to write to the Spack instance above.\n"
            + indent
            + "Please contact scisoft-team@fnal.gov for guidance."
        )

    # Create home repo if it doesn't exist
    local_dir = config.user_config_dir()
    local_dir.mkdir(exist_ok=True)
    full_path, _ = spack.repo.create_repo(
        str(local_dir), "local-mpd", spack.repo.packages_dir_name
    )
    AddArgs = namedtuple("args", ["path", "scope"])
    spack.cmd.repo.repo_add(AddArgs(path=full_path, scope="user"))

    config.selected_projects_dir().mkdir(exist_ok=True)
