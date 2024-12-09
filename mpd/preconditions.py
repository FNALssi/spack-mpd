from enum import Flag, auto

import llnl.util.tty as tty

import spack.environment as ev
import spack.environment.shell as ev_shell

from . import config, init
from .util import bold, cyan, gray, green


class State(Flag):
    INITIALIZED = auto()
    SELECTED_PROJECT = auto()
    PACKAGES_TO_DEVELOP = auto()
    ACTIVE_ENVIRONMENT = auto()


def test_bit(conditions, state):
    if state in conditions:
        return True
    if ~state in conditions:
        return False
    return None


def sign(flag):
    return "" if flag else bold(" not")


def check_initialized(conditions):
    should_be_initialized = test_bit(conditions, State.INITIALIZED)
    if should_be_initialized is None:
        return None
    if init.initialized() == should_be_initialized:
        return None
    if should_be_initialized is True:
        return f"MPD not initialized--invoke {bold('spack mpd init')}"
    return "MPD must not be initialized"


def check_selected(conditions):
    should_be_selected = test_bit(conditions, State.SELECTED_PROJECT)
    if should_be_selected is None:
        return None

    selected_project = config.selected_project()
    project_is_selected = selected_project is not None
    if project_is_selected and not should_be_selected:
        return (f"An MPD project must {bold('not')} be selected "
                f"({cyan(selected_project)} currently selected)")
    if not project_is_selected and should_be_selected:
        return "An MPD project must be selected"
    return None


def check_packages(conditions):
    should_be_packages = test_bit(conditions, State.PACKAGES_TO_DEVELOP)
    if should_be_packages is None:
        return None

    selected_project = config.selected_project(missing_ok=True)
    selected_config = config.project_config(selected_project)
    if not selected_config:
        return None  # This will be handled by a different check

    packages = selected_config["packages"]
    if packages and not should_be_packages:
        return f"There {bold('cannot')} be any repositories in {selected_config['source']}"
    if not packages and should_be_packages:
        return f"Repositories to develop must exist in {cyan(selected_config['source'])}"
    return None


def check_active(conditions):
    should_be_active = test_bit(conditions, State.ACTIVE_ENVIRONMENT)
    if should_be_active is None:
        return None

    active_env = ev.active_environment()
    active_env_name = active_env.name if active_env else ""
    selected_project = config.selected_project(missing_ok=True)
    selected_project_config = None
    if selected_project:
        selected_project_config = config.project_config(selected_project, missing_ok=True)

    if not selected_project_config:
        if should_be_active:
            return f"Cannot find configuration for selected project ({selected_project})."
        return None

    project_env_name = selected_project_config["local"]

    if not active_env_name:
        if should_be_active:
            if selected_project:
                return f"The Spack environment {cyan(project_env_name)} must be active"
            return "A Spack environment must be active"
        return None

    # In this case, an active environment is allowed so long as it's different
    # from the development environment of the selected project.
    if not should_be_active and active_env_name == project_env_name:
        return (f"The Spack environment {cyan(ev.active_environment().name)} "
                f"must {bold('not')} be active")

    # In this case, the active environment must be the same as the development
    # environment of the project.
    if should_be_active and active_env_name != project_env_name:
        return f"The Spack environment {cyan(project_env_name)} must be active."

    return None


def preconditions(*conditions):
    errors = []
    if initialization_precondition := check_initialized(conditions):
        errors.append(initialization_precondition)

    if selected_precondition := check_selected(conditions):
        errors.append(selected_precondition)

    if selected_precondition := check_packages(conditions):
        errors.append(selected_precondition)

    if active_precondition := check_active(conditions):
        errors.append(active_precondition)

    if errors:
        msg = "To execute the above command, the following preconditions must be met:"
        for e in errors:
            msg += f"\n - {e}"
        print()
        tty.die(msg + "\n")


def activate_development_environment(env_dir):
    development_env = ev.Environment(env_dir)
    active = ev.active_environment()
    print()
    if active and active.name == development_env.name:
        tty.msg(green("Using active development environment ") + gray(f"({development_env.name})"))
        return

    tty.msg(green("Activating development environment ") + gray(f"({development_env.name})"))
    ev_shell.activate(development_env).apply_modifications()
