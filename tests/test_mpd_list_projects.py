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
    assert "spack mpd info <project name>" in output


def test_list_rejects_details(with_mpd_init):
    command = SpackCommand("mpd")
    assert command("ls") == command("list")
    assert "unrecognized arguments" in command("list", "project", fail_on_error=False)
    assert command.returncode != 0
    assert "unrecognized arguments" in command("list", "--build", "project", fail_on_error=False)
    assert command.returncode != 0
    assert "unrecognized arguments" in command("ls", "--raw", "project", fail_on_error=False)
    assert command.returncode != 0
