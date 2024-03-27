def setup_subparser(subparsers):
    subparsers.add_parser(
        "install",
        description="install (and build if necessary) repositories",
        aliases=["i"],
        help="install built repositories",
    )
