from pathlib import Path

import pytest

import spack.util.spack_yaml as syaml
from spack.extensions.mpd import config, rm_project


def _project(name, top, source=None, build=None):
    return {
        "name": name,
        "top": str(top),
        "source": str(source or top / "srcs"),
        "build": str(build or top / "build"),
        "local": str(top / "local"),
    }


@pytest.mark.parametrize("has_environment", [False, True])
def test_safe_removal_deletes_managed_paths_and_all_selection_tokens(
    with_mpd_init, tmp_path, monkeypatch, has_environment
):
    top = tmp_path / "project"
    project = _project("project", top)
    for path in (Path(project["build"]), Path(project["local"]), top / ".mpd"):
        path.mkdir(parents=True, exist_ok=True)
    if has_environment:
        (Path(project["local"]) / "spack.yaml").write_text("spack: {}\n")
    config.update(project)
    selected = config.selected_projects_dir()
    selected.mkdir(exist_ok=True)
    (selected / "101").write_text("project")
    (selected / "102").write_text("project")
    commands = []
    monkeypatch.setattr(
        rm_project.subprocess, "run", lambda command, **kwargs: commands.append(command)
    )

    rm_project.rm_project("project", project)

    expected = [["spack", "env", "rm", "-y", project["local"]]] if has_environment else []
    assert commands == expected
    assert not Path(project["build"]).exists()
    assert not Path(project["local"]).exists()
    assert not (top / ".mpd").exists()
    assert config.mpd_config()["projects"] == {}
    assert list(selected.iterdir()) == []


def test_removal_overlap_preserves_all_managed_paths(with_mpd_init, tmp_path):
    departing_top = tmp_path / "departing"
    shared_build = tmp_path / "remaining" / "srcs" / "nested-build"
    projects = {
        "departing": _project("departing", departing_top, build=shared_build),
        "remaining": _project("remaining", tmp_path / "remaining"),
    }
    for role in config.PROTECTED_ROLES:
        path = config.project_paths(projects["departing"])[role]
        path.mkdir(parents=True, exist_ok=True)
    with open(config.mpd_config_file(), "w") as stream:
        syaml.dump({"projects": projects}, stream=stream)

    conflicts = config.removal_conflicts("departing", projects)
    assert conflicts
    rm_project.rm_project("departing", projects["departing"], cleanup=False)

    for role in config.PROTECTED_ROLES:
        assert config.project_paths(projects["departing"])[role].exists()
    assert "departing" not in config.mpd_config()["projects"]
