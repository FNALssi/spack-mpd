import os
import shutil

from .mrb_config import rm_config


def rm_project(name, config, full_removal):
    os.system(f"spack uninstall -y {name} >& /dev/null")
    os.system(f"spack uninstall -y {name}-bootstrap >& /dev/null")
    os.system(f"spack repo rm {name} >& /dev/null")
    shutil.rmtree(config["build"], ignore_errors=True)
    shutil.rmtree(config["local"], ignore_errors=True)
    if full_removal:
        shutil.rmtree(config["top"], ignore_errors=True)
    rm_config(name)
