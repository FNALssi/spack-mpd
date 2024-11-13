import importlib

from .. import config

description = "develop multiple packages using Spack for external software"
section = "developer"
level = "long"

_VERSION = "0.2.0"

subcommands = [
    "build",
    "clear",
    "clone",
    "init",
    "install",
    "list_projects",
    "new_project",
    "refresh",
    "rm_project",
    "select",
    "status",
    "test",
    "zap",
]
subcommand_modules = {
    scmd: importlib.import_module(f"..{scmd}", f"spack.extensions.mpd.{scmd}")
    for scmd in subcommands
}


def setup_parser(subparser):
    subparser.add_argument(
        "-V", "--version", action="store_true", help=f"print MPD version ({_VERSION}) and exit"
    )

    subparsers = subparser.add_subparsers(dest="mpd_subcommand", required=False)
    for m in subcommand_modules.values():
        m.setup_subparser(subparsers)


def mpd(parser, args):
    is_initialized = subcommand_modules["init"].initialized()
    for m in subcommand_modules.values():
        scmds = [m.SUBCOMMAND] + getattr(m, "ALIASES", [])
        if args.mpd_subcommand not in scmds:
            continue

        if args.mpd_subcommand != "init" and is_initialized:
            # Each non-init command either relies on the cached information in
            # the user configuration or the cached selected project (if it exists).
            config.update_cache()

        m.process(args)
        break

    if args.version:
        print("spack mpd", _VERSION)
