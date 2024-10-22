from enum import Flag, auto

import llnl.util.tty as tty

import spack.environment as ev

from . import config, init
from .util import bold, cyan


class State(Flag):
    INITIALIZED = auto()
    SELECTED_PROJECT = auto()
    ACTIVE_ENVIRONMENT = auto()


def test_bit(conditions, state):
    if state in conditions:
        return True
    if ~state in conditions:
        return False
    return None


def sign(flag):
    return "" if flag else bold(" not")


def preconditions(*conditions):
    should_be_initialized = test_bit(conditions, State.INITIALIZED)
    should_be_selected = test_bit(conditions, State.SELECTED_PROJECT)
    should_be_active = test_bit(conditions, State.ACTIVE_ENVIRONMENT)
    errors = []
    if should_be_initialized is not None:
        if init.initialized() != should_be_initialized:
            errors.append(f"MPD must{sign(should_be_initialized)} be initialized")

    if should_be_selected is not None:
        selected_project = config.selected_project()
        project_is_selected = selected_project is not None
        if project_is_selected and not should_be_selected:
            errors.append(f"An MPD project must {bold('not')} be selected "
                          f"({cyan(selected_project)} currently selected)")
        if not project_is_selected and should_be_selected:
            errors.append("An MPD project must be selected")

    if should_be_active is not None:
        active_env = ev.active_environment() is not None
        if active_env and not should_be_active:
            errors.append(f"A Spack environment must {bold('not')} be active "
                          f"({cyan(ev.active_environment().name)} currently active)")
        if not active_env and should_be_active:
            errors.append("A Spack environment must be active")

    if errors:
        msg = "To execute the above command, the following preconditions must be met:"
        for e in errors:
            msg += f"\n - {e}"
        print()
        tty.die(msg + "\n")
