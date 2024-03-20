import shutil
import subprocess
from pathlib import Path

from .mrb_config import mrb_packages, rm_config


def _run_no_output(*args):
    return subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _rm_packages(name):
    packages_path = Path(mrb_packages())
    if not packages_path.exists():
        return

    shutil.rmtree(packages_path / f"{name}-bootstrap", ignore_errors=True)
    shutil.rmtree(packages_path / f"{name}-mrb", ignore_errors=True)


def rm_project(name, config, full_removal):
    _run_no_output("spack", "env", "rm", "-y", name)
    _run_no_output("spack", "uninstall", "-y", f"{name}-mrb")
    _rm_packages(name)
    shutil.rmtree(config["build"], ignore_errors=True)
    shutil.rmtree(config["local"], ignore_errors=True)
    if full_removal:
        shutil.rmtree(config["top"], ignore_errors=True)
    rm_config(name)
