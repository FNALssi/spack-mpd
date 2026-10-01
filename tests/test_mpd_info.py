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


def test_info_defaults_to_selected_project(with_mpd_init, tmp_path, monkeypatch):
    top = tmp_path / "project"
    project = _project(top, top / "srcs")
    with open(config.mpd_config_file(), "w") as stream:
        syaml.dump({"projects": {"project": project}}, stream=stream)
    monkeypatch.setattr(config, "selected_project", lambda: "project")

    command = SpackCommand("mpd")
    assert "Details for project" in command("info")
    assert "name: project" in command("info", "--raw")
    paths = (("--top", top), ("--build", top / "build"), ("--source", top / "srcs"))
    for option, path in paths:
        assert command("info", option).strip() == str(path)


def test_info_explicit_project_overrides_selection(with_mpd_init, tmp_path, monkeypatch):
    selected = tmp_path / "selected"
    other = tmp_path / "other"
    projects = {
        "selected": _project(selected, selected / "srcs"),
        "other": _project(other, other / "srcs"),
    }
    with open(config.mpd_config_file(), "w") as stream:
        syaml.dump({"projects": projects}, stream=stream)
    monkeypatch.setattr(config, "selected_project", lambda: "selected")

    command = SpackCommand("mpd")
    assert "Details for other" in command("info", "other")
    assert command("info", "--top", "other").strip() == str(other)


def test_info_requires_project_without_selection(with_mpd_init, monkeypatch):
    monkeypatch.setattr(config, "selected_project", lambda: None)
    command = SpackCommand("mpd")
    assert "Specify a project name" in command("info", fail_on_error=False)
    assert command.returncode != 0
    assert "Specify a project name" in command("info", "--raw", fail_on_error=False)
    assert command.returncode != 0
    for option in ("--top", "--build", "--source"):
        assert "Specify a project name" in command("info", option, fail_on_error=False)
        assert command.returncode != 0
