import spack.util.spack_yaml as syaml
from spack.extensions.mpd import config
from spack.main import SpackCommand


def _project(top, source):
    return {
        "name": top.name,
        "top": str(top),
        "source": str(source),
        "build": str(top / "build"),
        "local": str(top / "local"),
        "packages": {},
        "ignored": [],
        "dependencies": {},
        "env": None,
    }


def test_list_annotates_shared_canonical_sources(with_mpd_init, tmp_path):
    source = tmp_path / "shared"
    projects = {
        "debug": _project(tmp_path / "debug", source / ".." / "shared"),
        "release": _project(tmp_path / "release", source),
    }
    with open(config.mpd_config_file(), "w") as stream:
        syaml.dump({"projects": projects}, stream=stream)

    output = SpackCommand("mpd")("list")

    assert "Shared source with: release" in output
    assert "Shared source with: debug" in output
    assert output.count(str(source)) == 2


def test_raw_details_preserve_stored_path(with_mpd_init, tmp_path):
    stored_top = str(tmp_path / "project" / ".." / "project")
    shared = tmp_path / "project" / "srcs"
    project = _project(tmp_path / "project", shared)
    project["top"] = stored_top
    peer = _project(tmp_path / "peer", shared)
    with open(config.mpd_config_file(), "w") as stream:
        syaml.dump({"projects": {"project": project, "peer": peer}}, stream=stream)

    output = SpackCommand("mpd")("list", "project", "--raw")

    assert stored_top in output
