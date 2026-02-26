import importlib

import spack.llnl.util.tty as tty

from .. import config

description = "develop multiple packages using Spack for external software"
section = "developer"
level = "long"

_VERSION = "0.3.0"

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
    "cmd_select",  # prefix with cmd_ to avoid collision with standard library select
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


def _all_subcommand_tokens():
    tokens = set()
    for m in subcommand_modules.values():
        tokens.add(m.SUBCOMMAND)
        tokens.update(getattr(m, "ALIASES", []))
    return tokens


def _check_for_multiple_subcommands(args):
    if not args.mpd_subcommand:
        return

    tokens = _all_subcommand_tokens()
    extra = []
    for value in vars(args).values():
        # Only check list-type arguments for now.  This is a kludgy way of looking for positional
        # arguments to the MPD subcommands, which are currently the only way to specify multiple
        # subcommands at once.  If we later add options that can also be used to specify multiple
        # subcommands, we may want to revisit this logic.
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, str) and item in tokens:
                extra.append(item)

    if extra:
        extra_str = ", ".join(f"'{e}'" for e in extra)
        tty.die(
            f"Only one subcommand may be specified at a time."
            f" The following are known MPD subcommands, not arguments to"
            f" '{args.mpd_subcommand}': {extra_str}"
        )


def mpd(parser, args):
    _check_for_multiple_subcommands(args)

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
