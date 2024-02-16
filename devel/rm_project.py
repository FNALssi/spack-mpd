import shutil
import subprocess

from .mrb_config import rm_config


def _run_no_output(*args):
    return subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def rm_project(name, config, full_removal):
    _run_no_output("spack", "uninstall", "-y", name)
    _run_no_output("spack", "uninstall", "-y", f"{name}-bootstrap")
    _run_no_output("spack", "repo", "rm", name)
    shutil.rmtree(config["build"], ignore_errors=True)
    shutil.rmtree(config["local"], ignore_errors=True)
    if full_removal:
        shutil.rmtree(config["top"], ignore_errors=True)
    rm_config(name)
