from . import init
from . import config
from .util import bold

from enum import Flag, auto
import llnl.util.tty as tty

import spack.environment as ev


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
        project_is_selected = config.selected_project() is not None
        if project_is_selected != should_be_selected:
            errors.append(f"An MPD project must{sign(should_be_selected)} be selected")

    if should_be_active is not None:
        active_env = ev.active_environment() is not None
        if active_env != should_be_active:
            errors.append(f"A Spack environment must{sign(should_be_active)} be active")

    if errors:
        msg = "To execute the above command, the following preconditions must be met:"
        for e in errors:
            msg += f"\n - {e}"
        print()
        tty.die(msg + "\n")
