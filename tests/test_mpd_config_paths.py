from pathlib import Path

import pytest

import spack.util.spack_yaml as syaml
from spack.extensions.mpd import config, preconditions


def project(top, source=None, build=None, local=None):
    top = Path(top)
    return {
        "top": str(top),
        "source": str(source or top / "srcs"),
        "build": str(build or top / "build"),
        "local": str(local or top / "local"),
    }


def test_canonical_path_resolves_nonexistent_path_and_symlink_prefix(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)

    assert config.canonical_path(alias / "missing" / ".." / "source") == real / "source"


def test_path_relationship_includes_equality_and_both_containment_directions(tmp_path):
    parent = tmp_path / "parent"
    child = parent / "child"

    assert config.path_relationship(parent, parent) == "equal"
    assert config.path_relationship(parent, child) == "contains"
    assert config.path_relationship(child, parent) == "contained-by"
    assert config.path_relationship(parent, tmp_path / "other") is None


def test_disjoint_projects_have_no_conflicts(tmp_path):
    projects = {
        "debug": project(tmp_path / "debug"),
        "release": project(tmp_path / "release"),
    }

    assert config.layout_conflicts(projects) == ()


def test_exact_external_source_sharing_is_allowed(tmp_path):
    source = tmp_path / "shared"
    projects = {
        "debug": project(tmp_path / "debug", source=source),
        "release": project(tmp_path / "release", source=source),
    }

    assert config.layout_conflicts(projects) == ()
    assert config.shared_source_peers("debug", projects) == ("release",)


def test_shared_source_beneath_top_marks_all_owners_invalid(tmp_path):
    debug_top = tmp_path / "debug"
    source = debug_top / "srcs"
    projects = {
        "debug": project(debug_top, source=source),
        "release": project(tmp_path / "release", source=source),
    }

    conflicts = config.layout_conflicts(projects)

    assert len(conflicts) == 2
    assert config.invalid_projects(conflicts) == {"debug", "release"}
    assert {(item.first_project, item.second_project) for item in conflicts} == {
        ("debug", "debug"),
        ("debug", "release"),
    }


def test_protected_and_source_overlap_is_rejected(tmp_path):
    projects = {
        "alpha": project(tmp_path / "alpha", build=tmp_path / "shared" / "build"),
        "beta": project(tmp_path / "beta", source=tmp_path / "shared"),
    }

    conflicts = config.layout_conflicts(projects)

    assert len(conflicts) == 1
    assert conflicts[0].relationship == "contained-by"
    assert {conflicts[0].first_role, conflicts[0].second_role} == {"build", "source"}


@pytest.mark.parametrize("first_role", config.PROTECTED_ROLES)
@pytest.mark.parametrize("second_role", config.PROTECTED_ROLES)
@pytest.mark.parametrize("reverse", [False, True])
def test_all_protected_role_overlaps_are_rejected(tmp_path, first_role, second_role, reverse):
    projects = {
        "alpha": project(tmp_path / "alpha"),
        "beta": project(tmp_path / "beta"),
    }
    if first_role == "metadata":
        first_path = tmp_path / "overlap" / ".mpd"
        second_path = first_path / "nested" / (".mpd" if second_role == "metadata" else second_role)
    elif second_role == "metadata":
        second_path = tmp_path / "overlap" / ".mpd"
        first_path = second_path / "nested" / first_role
    else:
        first_path = tmp_path / "overlap"
        second_path = first_path / "nested"
    if reverse:
        first_path, second_path = second_path, first_path

    if first_role == "metadata":
        projects["alpha"]["top"] = str(first_path.parent)
    else:
        projects["alpha"][first_role] = str(first_path)
    if second_role == "metadata":
        projects["beta"]["top"] = str(second_path.parent)
    else:
        projects["beta"][second_role] = str(second_path)

    conflicts = config.layout_conflicts(projects)

    assert any(
        {item.first_role, item.second_role} == {first_role, second_role}
        or item.first_role == item.second_role == first_role == second_role
        for item in conflicts
    )


@pytest.mark.parametrize("protected_role", config.PROTECTED_ROLES)
@pytest.mark.parametrize("reverse", [False, True])
def test_all_protected_source_overlaps_are_rejected(tmp_path, protected_role, reverse):
    projects = {
        "alpha": project(tmp_path / "alpha"),
        "beta": project(tmp_path / "beta"),
    }
    protected_path = tmp_path / "overlap" / (".mpd" if protected_role == "metadata" else protected_role)
    source_path = protected_path / "nested"
    if reverse:
        source_path = tmp_path / "overlap"
        protected_path = source_path / "nested" / (
            ".mpd" if protected_role == "metadata" else protected_role
        )
    if protected_role == "metadata":
        projects["alpha"]["top"] = str(protected_path.parent)
    else:
        projects["alpha"][protected_role] = str(protected_path)
    projects["beta"]["source"] = str(source_path)

    conflicts = config.layout_conflicts(projects)

    assert any(
        {item.first_role, item.second_role} == {protected_role, "source"}
        for item in conflicts
    )


def test_nested_sources_are_rejected(tmp_path):
    projects = {
        "alpha": project(tmp_path / "alpha", source=tmp_path / "sources"),
        "beta": project(tmp_path / "beta", source=tmp_path / "sources" / "nested"),
    }

    conflicts = config.layout_conflicts(projects)

    assert len(conflicts) == 1
    assert conflicts[0].first_role == conflicts[0].second_role == "source"


def test_invalid_canonicalization_is_not_persisted(with_mpd_init, tmp_path):
    stored = {
        "projects": {
            "alpha": project(tmp_path / "alpha", source=tmp_path / "shared" / ".." / "shared"),
            "beta": project(tmp_path / "beta", source=tmp_path / "shared"),
        }
    }
    # Make the shared source invalid by locating it beneath alpha's top.
    stored["projects"]["alpha"]["source"] = str(tmp_path / "alpha" / "srcs" / ".." / "srcs")
    stored["projects"]["beta"]["source"] = str(tmp_path / "alpha" / "srcs")
    with open(config.mpd_config_file(), "w") as stream:
        syaml.dump(stored, stream=stream)

    loaded = config.mpd_config()
    raw = config.mpd_config(raw=True)

    assert loaded["projects"]["alpha"]["source"] == str(tmp_path / "alpha" / "srcs")
    assert raw["projects"]["alpha"]["source"].endswith("srcs/../srcs")


def test_valid_canonicalization_is_persisted(with_mpd_init, tmp_path):
    stored = {"projects": {"alpha": project(tmp_path / "alpha" / ".." / "alpha")}}
    with open(config.mpd_config_file(), "w") as stream:
        syaml.dump(stored, stream=stream)

    loaded = config.mpd_config()
    raw = config.mpd_config(raw=True)

    assert loaded["projects"]["alpha"]["top"] == str(tmp_path / "alpha")
    assert raw["projects"]["alpha"]["top"] == str(tmp_path / "alpha")


def test_mutation_guard_blocks_only_conflicting_project(monkeypatch, tmp_path):
    projects = {
        "alpha": project(tmp_path / "alpha", source=tmp_path / "shared"),
        "beta": project(tmp_path / "beta", source=tmp_path / "shared" / "nested"),
        "gamma": project(tmp_path / "gamma"),
    }
    monkeypatch.setattr(config, "mpd_config", lambda: {"projects": projects})

    monkeypatch.setattr(config, "selected_project", lambda missing_ok=True: "alpha")
    with pytest.raises(SystemExit):
        preconditions.require_safe_project_mutation()

    monkeypatch.setattr(config, "selected_project", lambda missing_ok=True: "gamma")
    preconditions.require_safe_project_mutation()
