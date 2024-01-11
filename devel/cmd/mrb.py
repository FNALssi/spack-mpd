description = "create multi-repository build area"
section = "scripting"
level = "long"

from ..functions import process


def setup_parser(subparser):
    subparser.add_argument('--name', required=True)
    subparser.add_argument('--top', required=True)
    subparser.add_argument('-D', '--dir', required=True)
    subparser.add_argument('variants', nargs='*')


def mrb(parser, args):
    process_args(args.name, args.top, args.dir, args.variants)
