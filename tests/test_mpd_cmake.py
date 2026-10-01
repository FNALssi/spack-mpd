import json
from pathlib import Path

from spack.extensions.mpd import build, concretize


def project(tmp_path):
    top = tmp_path / "project"
    source = tmp_path / "shared sources"
    top.mkdir()
    source.mkdir()
    return {
        "name": "example",
        "top": str(top),
        "source": str(source),
        "build": str(top / "build"),
        "local": str(top / "local"),
        "srcs": {"package": "package"},
        "compiler_paths": {},
        "cxxstd": {"value": "17"},
        "languages": [],
    }


def test_cmake_files_are_written_to_metadata(monkeypatch, tmp_path):
    cfg = project(tmp_path)
    package_source = Path(cfg["source"]) / "package"
    package_source.mkdir()
    package_presets = {"version": 3, "configurePresets": []}
    (package_source / "CMakePresets.json").write_text(json.dumps(package_presets))
    monkeypatch.setattr(concretize, "runtime_library_dirs", lambda _: [])

    concretize.make_cmake_files(
        cfg,
        {},
        [("package", "hash", "/install/prefix")],
        cetmodules4=False,
        view_path=tmp_path / "view",
    )

    metadata = Path(cfg["top"]) / ".mpd"
    assert (metadata / "CMakeLists.txt").exists()
    assert (metadata / "develop.cmake").exists()
    assert (metadata / "CMakePresets.json").exists()
    assert not (Path(cfg["source"]) / "CMakeLists.txt").exists()
    develop = (metadata / "develop.cmake").read_text()
    assert 'add_subdirectory("${MPD_SOURCE_DIR}/${pkg}" "${CMAKE_BINARY_DIR}/${pkg}")' in develop


def test_package_presets_use_checkout_directory_name(monkeypatch, tmp_path):
    cfg = project(tmp_path)
    cfg["srcs"] = {"package": "checkout-name"}
    checkout = Path(cfg["source"]) / "checkout-name"
    checkout.mkdir()
    (checkout / "CMakePresets.json").write_text(
        json.dumps(
            {
                "version": 3,
                "configurePresets": [
                    {"name": "default", "cacheVariables": {"package_OPTION": "ON"}}
                ],
            }
        )
    )
    monkeypatch.setattr(concretize, "runtime_library_dirs", lambda _: [])

    concretize.make_cmake_files(
        cfg,
        {},
        [("package", "hash", "/install/prefix")],
        cetmodules4=False,
        view_path=tmp_path / "view",
    )

    presets = json.loads((Path(cfg["top"]) / ".mpd" / "CMakePresets.json").read_text())
    assert presets["configurePresets"][0]["cacheVariables"]["package_OPTION"] == "ON"
    lists = (Path(cfg["top"]) / ".mpd" / "CMakeLists.txt").read_text()
    assert 'develop("checkout-name")' in lists


def test_legacy_cmake_files_are_preserved_and_warned(monkeypatch, tmp_path, capsys):
    cfg = project(tmp_path)
    legacy = Path(cfg["source"]) / "CMakeLists.txt"
    legacy.write_text("user-owned")
    monkeypatch.setattr(concretize, "runtime_library_dirs", lambda _: [])

    concretize.make_cmake_files(cfg, {}, [], cetmodules4=False, view_path=tmp_path / "view")

    assert legacy.read_text() == "user-owned"
    assert str(legacy) in capsys.readouterr().err


def test_configure_uses_metadata_as_source(monkeypatch, tmp_path):
    cfg = project(tmp_path)
    cfg["generator"] = {"value": "ninja"}
    captured = {}
    monkeypatch.setattr(build.subprocess, "run", lambda command: captured.setdefault("command", command))

    build.configure_cmake_project(cfg)

    assert captured["command"][3] == str(Path(cfg["top"]) / ".mpd")
    assert captured["command"][5] == cfg["build"]


def test_cmake_string_escapes_significant_characters():
    assert concretize.cmake_string('a b\\c;d"${HOME}') == 'a b\\\\c\\;d\\"\\${HOME}'
