import pytest

import spack
from spack.extensions.mpd import config, init
from spack.main import SpackCommand


@pytest.fixture
def tmp_mpd_dir(tmp_path_factory):
    real_path = config.mpd_config_dir()
    path_for_test = tmp_path_factory.mktemp("mpd")
    with pytest.MonkeyPatch.context() as m:
        mpd_dir = (path_for_test / "init").resolve()
        m.setattr(init, "MPD_DIR", mpd_dir)
        yield mpd_dir
    spack.config.set("config:mpd_dir", str(real_path))


@pytest.fixture
def with_mpd_init(tmp_mpd_dir):
    SpackCommand("mpd")("init")
    yield
