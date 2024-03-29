import sys

import llnl.util.tty as tty


def bold(msg):
    return tty.color.colorize("@*{" + msg + "}")


def maybe_with_color(color, msg):
    if not color:
        return msg
    return tty.color.colorize(f"@{color}" + "{" + msg + "}")


def spack_cmd_line():
    # We specify 'spack' instead of using argv[0], which can include
    # the entire path of the executable.
    return f"spack {' '.join(sys.argv[1:])}"
