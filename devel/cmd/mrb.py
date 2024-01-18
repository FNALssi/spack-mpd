description = "create multi-repository build area"
section = "scripting"
level = "long"

from ..new_dev import new_dev
from ..suites import help_suites

def setup_parser(subparser):
    subparsers = subparser.add_subparsers(dest="mrb_subcommand")
    build = subparsers.add_parser("build",
                                  description="build repositories under development",
                                  aliases=["b"],
                                  help="build repositories")

    git = subparsers.add_parser("git-clone",
                                description="clone git repositories for development",
                                aliases=["g", "gitCheckout"],
                                help="clone git repositories")
    git.add_argument('--suite')
    git.add_argument('--help-suites', action='store_true', help="list supported suites")

    install = subparsers.add_parser("install",
                                    description="install (and build if necessary) repositories",
                                    aliases=["i"],
                                    help="install built repositories")
    newDev = subparsers.add_parser("new-dev",
                                   description="create new development area",
                                   aliases=["n", "newDev"],
                                   help="create new development area")
    newDev.add_argument('--name', required=True)
    newDev.add_argument('--top', required=True)
    newDev.add_argument('-D', '--dir', required=True)
    newDev.add_argument('variants', nargs='*')

    test = subparsers.add_parser("test",
                                 description="build and run tests",
                                 aliases=["t"],
                                 help="build and run tests")
    zap = subparsers.add_parser("zap-build",
                                 description="delete everything in your build area",
                                 aliases=["z", "zapBuild"],
                                 help="delete everything in your build area")



def mrb(parser, args):
    if args.mrb_subcommand in ("new-dev", "n"):
        new_dev(args.name, args.top, args.dir, args.variants)
        return
    if args.mrb_subcommand in ("git-clone", "g"):
        help_suites()
        return
