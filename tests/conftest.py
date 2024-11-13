import pytest

import spack
from spack.extensions.mpd import config, init
from spack.main import SpackCommand


@pytest.fixture
def tmp_mpd_dir(tmp_path_factory):
    project = config.selected_project()
    real_path = config.mpd_config_dir(missing_ok=True)
    path_for_test = tmp_path_factory.mktemp("mpd")
    mpd_dir = (path_for_test / "init").resolve()
    with pytest.MonkeyPatch.context() as m:
        m.setattr(init, "MPD_DIR", mpd_dir)
        yield mpd_dir
    if not real_path:
        SpackCommand("config")("--scope", "site", "rm", "config:mpd_dir")
    else:
        spack.config.set("config:mpd_dir", str(real_path), scope="site")
    if project:
        config.select(project)


@pytest.fixture
def with_mpd_init(tmp_mpd_dir):
    SpackCommand("mpd")("init")
    yield
