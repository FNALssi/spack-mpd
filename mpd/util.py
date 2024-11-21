import sys
from pathlib import Path

import llnl.util.tty as tty

import spack.util.spack_yaml as syaml


def bold(msg):
    return tty.color.colorize(f"@*{{{msg}}}")


def cyan(msg):
    return tty.color.colorize(f"@c{{{msg}}}")


def gray(msg):
    return tty.color.colorize(f"@K{{{msg}}}")


def green(msg):
    return tty.color.colorize(f"@g{{{msg}}}")


def magenta(msg):
    return tty.color.colorize(f"@M{{{msg}}}")


def yellow(msg):
    return tty.color.colorize(f"@y{{{msg}}}")


def get_number(prompt, **kwargs):
    default = kwargs.get("default", None)
    abort = kwargs.get("abort", None)

    if default is not None and abort is not None:
        prompt += " (default is %s, %s to abort) " % (default, abort)
    elif default is not None:
        prompt += " (default is %s) " % default
    elif abort is not None:
        prompt += " (%s to abort) " % abort

    number = None
    while number is None:
        tty.msg(prompt, newline=False)
        ans = input()
        if ans == str(abort):
            return None

        if ans:
            try:
                number = int(ans)
                if number < 1:
                    tty.msg("Please enter a valid number.")
                    number = None
            except ValueError:
                tty.msg("Please enter a valid number.")
        elif default is not None:
            number = default
    return number


def make_yaml_file(package, spec, prefix):
    filepath = Path(f"{package}.yaml")
    if prefix:
        filepath = prefix / filepath
    with open(filepath, "w") as f:
        syaml.dump(spec, stream=f, default_flow_style=False)
    return str(filepath)


def maybe_with_color(color, msg):
    if not color:
        return msg
    return tty.color.colorize(f"@{color}" + "{" + msg + "}")


def spack_cmd_line():
    # We specify 'spack' instead of using argv[0], which can include
    # the entire path of the executable.
    return f"spack {' '.join(sys.argv[1:])}"
