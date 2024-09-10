import pytest

import spack
from spack.extensions.mpd import config, init
from spack.main import SpackCommand


@pytest.fixture(scope="module")
def tmp_mpd_dir(tmp_path_factory):
    real_path = config.mpd_config_dir()
    path_for_test = tmp_path_factory.mktemp("init")
    with pytest.MonkeyPatch.context() as m:
        m.setattr(init, "MPD_DIR", path_for_test)
        yield str(path_for_test)
    spack.config.set("config:mpd_dir", str(real_path))


@pytest.fixture(scope="module")
def with_mpd_init(tmp_mpd_dir):
    SpackCommand("mpd")("init")
    yield
    SpackCommand("repo")("rm", "--scope=site", str(config.mpd_config_dir()))
