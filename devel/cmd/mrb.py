description = "create multi-repository build area"
section = "scripting"
level = "long"

from ..new_dev import new_dev
from ..suites import help_suites

def setup_parser(subparser):
    subparsers = subparser.add_subparsers(dest="mrb_subcommand")
    newDev = subparsers.add_parser("new-dev",
                                   description="create new development area",
                                   aliases=["n"],
                                   help="create new development area")
    newDev.add_argument('--name', required=True)
    newDev.add_argument('--top', required=True)
    newDev.add_argument('-D', '--dir', required=True)
    newDev.add_argument('variants', nargs='*')

    git = subparsers.add_parser("git-clone",
                                description="clone git repositories for development",
                                aliases=["g"],
                                help="clone git repositories")
    git.add_argument('--suite')
    git.add_argument('--help-suites', action='store_true', help="list supported suites")

    build = subparsers.add_parser("build",
                                  description="build repositories under development",
                                  aliases=["b"],
                                  help="SHOULD WE PROVIDE THIS?")

def mrb(parser, args):
    if args.mrb_subcommand in ("new-dev", "n"):
        new_dev(args.name, args.top, args.dir, args.variants)
        return
    if args.mrb_subcommand in ("git-clone", "g"):
        help_suites()
        return
