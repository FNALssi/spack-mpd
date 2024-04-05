from pathlib import Path
import pytest

from spack.extensions.mpd import config
from spack.main import SpackCommand


@pytest.fixture(scope="module")
def tmp_home_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp("init")
    with pytest.MonkeyPatch.context() as m:
        m.setattr(Path, "home", lambda: path)
        yield


@pytest.fixture(scope="module")
def with_mpd_init(tmp_home_dir):
    SpackCommand("mpd")("init")
    yield
    SpackCommand("repo")("rm", str(config.user_config_dir()))
