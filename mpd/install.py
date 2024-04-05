SUBCOMMAND = "install"
ALIASES = ["i"]


def setup_subparser(subparsers):
    subparsers.add_parser(
        SUBCOMMAND,
        description="install (and build if necessary) repositories",
        aliases=ALIASES,
        help="install built repositories",
    )
