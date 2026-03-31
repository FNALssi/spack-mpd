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


def remove_dir(dir_path, keep_dir=False):
    """Remove a directory with retry logic for macOS .DS_Store issues.

    If `keep_dir` is True, keep the top-level directory but remove all of its
    contents. Retries on macOS to work around .DS_Store locking issues.
    """
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

        # Now remove either the directory or only its contents
        if keep_dir:
            if not dir_path.exists():
                break
            for child in list(dir_path.iterdir()):
                subprocess.run(
                    ["rm", "-rf", str(child)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        else:
            subprocess.run(
                ["rm", "-rf", str(dir_path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        # Check if removal succeeded
        if keep_dir:
            # Success when directory exists and is empty, or when it no longer exists
            if not dir_path.exists():
                break
            try:
                next(dir_path.iterdir())
                # Has children, not yet successful
                success = False
            except StopIteration:
                success = True

            if success:
                break
        else:
            if not dir_path.exists():
                break

        # Wait before retry (only on non-final attempts)
        if attempt < max_attempts - 1:
            time.sleep(0.1)

    # If removal didn't reach the intended state after attempts, log a warning
    if keep_dir:
        if dir_path.exists() and any(dir_path.iterdir()):
            tty.warn(f"Failed to remove contents of directory {dir_path} after {max_attempts} attempts")
    else:
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
