import spack.config
import spack.environment as ev

try:
    import spack.llnl.util.filesystem as fs
except ImportError:
    import spack.util.filesystem as fs

try:
    import spack.llnl.util.tty as tty

    if not hasattr(tty, "msg"):
        # spack.llnl.util.tty exists as an empty namespace package in some
        # Spack versions; fall back to the real module in that case.
        raise ImportError("spack.llnl.util.tty is an empty namespace package")
except ImportError:
    import spack.util.tty as tty


def config_get(path, default=None, scope=None):
    if hasattr(spack.config, "get"):
        return spack.config.get(path, default, scope=scope)

    if hasattr(spack.config, "CONFIG") and hasattr(spack.config.CONFIG, "get"):
        return spack.config.CONFIG.get(path, default=default, scope=scope)

    raise AttributeError("spack.config has no supported get API")


def config_set(path, value, scope=None):
    if hasattr(spack.config, "set"):
        return spack.config.set(path, value, scope=scope)

    if hasattr(spack.config, "CONFIG") and hasattr(spack.config.CONFIG, "set"):
        return spack.config.CONFIG.set(path, value, scope=scope)

    raise AttributeError("spack.config has no supported set API")


def active_environment():
    if hasattr(ev, "active_environment"):
        return ev.active_environment()

    if hasattr(ev, "get_active_environment"):
        return ev.get_active_environment()

    return None
