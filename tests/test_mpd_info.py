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


def test_raw_details_preserve_stored_path(with_mpd_init, tmp_path):
    stored_top = str(tmp_path / "project" / ".." / "project")
    shared = tmp_path / "project" / "srcs"
    project = _project(tmp_path / "project", shared)
    project["top"] = stored_top
    peer = _project(tmp_path / "peer", shared)
    with open(config.mpd_config_file(), "w") as stream:
        syaml.dump({"projects": {"project": project, "peer": peer}}, stream=stream)

    output = SpackCommand("mpd")("info", "project", "--raw")

    assert stored_top in output


def test_info_paths_and_details(with_mpd_init, tmp_path):
    top = tmp_path / "project"
    project = _project(top, top / "srcs")
    with open(config.mpd_config_file(), "w") as stream:
        syaml.dump({"projects": {"project": project}}, stream=stream)

    command = SpackCommand("mpd")
    assert "Details for project" in command("info", "project")
    paths = (("--top", top), ("--build", top / "build"), ("--source", top / "srcs"))
    for option, path in paths:
        assert command("info", option, "project").strip() == str(path)


def test_info_requires_target(with_mpd_init):
    command = SpackCommand("mpd")
    assert "Specify a project name" in command("info", fail_on_error=False)
    assert command.returncode != 0
    assert "Specify a project name" in command("info", "--raw", fail_on_error=False)
    assert command.returncode != 0
