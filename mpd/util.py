import subprocess
import sys
import time
from pathlib import Path

import spack.llnl.util.tty as tty
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


def remove_dir(dir_path):
    """Remove a directory with retry logic for macOS .DS_Store issues."""
    # On macOS, retry removal due to .DS_Store file issues
    max_attempts = 3 if sys.platform == "darwin" else 1

    for attempt in range(max_attempts):
        # First remove .DS_Store files that macOS creates
        if sys.platform == "darwin":
            subprocess.run(
                ["find", str(dir_path), "-name", ".DS_Store", "-delete"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        # Now remove the directory
        subprocess.run(
            ["rm", "-rf", str(dir_path)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Check if removal succeeded
        if not dir_path.exists():
            break

        # Wait before retry (only on non-final attempts)
        if attempt < max_attempts - 1:
            time.sleep(0.1)

    # If the directory still exists after all attempts, log a warning
    if dir_path.exists():
        tty.warn(f"Failed to remove directory {dir_path} after {max_attempts} attempts")


def remove_view(local_env_dir):
    spack_env = Path(local_env_dir) / ".spack-env"
    view_path = spack_env / "view"
    dotview_path = spack_env / "._view"

    # Remove view symlink
    if view_path.is_symlink():
        view_path.unlink()

    # Remove ._view directory
    if dotview_path.exists():
        remove_dir(dotview_path)
