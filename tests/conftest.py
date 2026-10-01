import pytest

from spack.extensions.mpd import config, init
from spack.extensions.mpd.spack_compat import config_set
from spack.main import SpackCommand
from spack.spec import Spec


@pytest.fixture(scope="module")
def tmp_mpd_dir(tmp_path_factory):
    real_path = init.mpd_config_dir()
    path_for_test = tmp_path_factory.mktemp("mpd")
    config_set("config:mpd_dir", str(path_for_test), scope="site")

    yield

    if real_path:
        config_set("config:mpd_dir", str(real_path), scope="site")
    else:
        SpackCommand("config")("--scope", "site", "rm", "config:mpd_dir")


@pytest.fixture
def available_compilers(monkeypatch):
    # Exercise compiler selection without querying the user's installation database.
    compilers = [Spec("gcc@=12.2.0"), Spec("gcc@=13.2.0"), Spec("clang@=16.0.0")]
    for compiler in compilers:
        compiler.external_path = "/usr"
        compiler.extra_attributes = {"compilers": {"c": "/usr/bin/cc", "cxx": "/usr/bin/c++"}}
    monkeypatch.setattr(config, "all_available_compilers", lambda: compilers)
    return compilers


@pytest.fixture
def with_mpd_init(tmp_mpd_dir, available_compilers):
    SpackCommand("mpd")("init")
    yield
