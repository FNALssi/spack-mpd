import spack.config
import spack.environment as ev
import spack.store

try:
    from spack.spec_parser import SpecParser, SpecTokens
except ImportError:
    from collections import namedtuple
    from enum import Enum

    from spack.spec import Spec
    from spack.spec_parser import SpecParser as SpackSpecParser

    class SpecTokens(Enum):
        KEY_VALUE_PAIR = "KEY_VALUE_PAIR"
        PROPAGATED_KEY_VALUE_PAIR = "PROPAGATED_KEY_VALUE_PAIR"
        BOOL_VARIANT = "BOOL_VARIANT"
        PROPAGATED_BOOL_VARIANT = "PROPAGATED_BOOL_VARIANT"
        VERSION = "VERSION"
        DEPENDENCY = "DEPENDENCY"
        START_EDGE_PROPERTIES = "START_EDGE_PROPERTIES"
        END_EDGE_PROPERTIES = "END_EDGE_PROPERTIES"
        UNQUALIFIED_PACKAGE_NAME = "UNQUALIFIED_PACKAGE_NAME"
        FULLY_QUALIFIED_PACKAGE_NAME = "FULLY_QUALIFIED_PACKAGE_NAME"
        DAG_HASH = "DAG_HASH"
        FILENAME = "FILENAME"
        WHEN = "WHEN"

    _SpecToken = namedtuple("SpecToken", "kind value")

    class SpecParser:
        """Expose MPD's token interface for Spack's regex-based parser."""

        def __init__(self, literal_str):
            self.parser = SpackSpecParser(literal_str, Spec)

        def tokens(self):
            for kind, value, groups in self.parser.tokens(with_subgroups=True):
                if kind == "BOOL_VARIANT" and groups["bv_prefix"] in ("++", "~~", "--"):
                    kind = "PROPAGATED_BOOL_VARIANT"
                elif kind == "KEY_VALUE_PAIR" and groups["kv_sep"].endswith("=="):
                    kind = "PROPAGATED_KEY_VALUE_PAIR"
                elif kind == "DEPENDENCY":
                    if value.startswith("^"):
                        sigil = "^"
                    else:
                        sigil = "%%" if value.startswith("%%") else "%"
                    yield _SpecToken(SpecTokens.DEPENDENCY, sigil)
                    if groups.get("edge_bracket"):
                        yield _SpecToken(SpecTokens.START_EDGE_PROPERTIES, "[")
                    elif groups.get("edge_virtuals"):
                        yield _SpecToken(SpecTokens.START_EDGE_PROPERTIES, "[")
                        yield _SpecToken(
                            SpecTokens.KEY_VALUE_PAIR, "virtuals=" + groups["edge_virtuals"]
                        )
                        yield _SpecToken(SpecTokens.END_EDGE_PROPERTIES, "]")
                        yield _SpecToken(
                            SpecTokens.UNQUALIFIED_PACKAGE_NAME, groups["edge_substitute"]
                        )
                    continue
                elif kind == "END_EDGE_PROPERTIES":
                    yield _SpecToken(SpecTokens.END_EDGE_PROPERTIES, "]")
                    if groups.get("edge_reopen"):
                        yield _SpecToken(SpecTokens.START_EDGE_PROPERTIES, "[")
                    elif groups.get("end_edge_virtuals"):
                        yield _SpecToken(SpecTokens.START_EDGE_PROPERTIES, "[")
                        yield _SpecToken(
                            SpecTokens.KEY_VALUE_PAIR, "virtuals=" + groups["end_edge_virtuals"]
                        )
                        yield _SpecToken(SpecTokens.END_EDGE_PROPERTIES, "]")
                        yield _SpecToken(
                            SpecTokens.UNQUALIFIED_PACKAGE_NAME, groups["end_edge_substitute"]
                        )
                    continue
                yield _SpecToken(SpecTokens[kind], value)


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


def install_status(spec):
    """Return the installation status of a spec across Spack versions."""
    if hasattr(spec, "install_status"):
        return spec.install_status()

    return spack.store.STORE.db.install_status(spec)
