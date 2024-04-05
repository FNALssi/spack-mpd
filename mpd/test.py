SUBCOMMAND = "test"
ALIASES = ["t"]


def setup_subparser(subparsers):
    subparsers.add_parser(
        SUBCOMMAND, description="build and run tests", aliases=ALIASES, help="build and run tests"
    )
