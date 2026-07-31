import pytest

from spack.extensions.mpd import init
from spack.extensions.mpd.spack_compat import config_set
from spack.main import SpackCommand


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
def with_mpd_init(tmp_mpd_dir):
    SpackCommand("mpd")("init")
    yield
