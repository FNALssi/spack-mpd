def setup_subparser(subparsers):
    subparsers.add_parser(
        "test", description="build and run tests", aliases=["t"], help="build and run tests"
    )
