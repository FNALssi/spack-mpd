import types

from spack.extensions.mpd import build


def test_build_targets_from_packages_accepts_repo_or_package_name(tmp_path):
    source_path = tmp_path / "srcs"
    source_path.mkdir()
    (source_path / "phlex").mkdir()
    (source_path / "phlex-examples").mkdir()

    project_config = {
        "source": str(source_path),
        "generator": {"value": "ninja"},
        "srcs": {
            "phlex": "phlex",
            "phlex_examples": "phlex-examples",
        },
    }

    targets = build.build_targets_from_packages(project_config, ["phlex_examples", "phlex"])

    assert targets == ["phlex-examples/all", "phlex/all"]


def test_build_includes_targets_before_generator_options(monkeypatch):
    captured = {}

    def fake_run(args):
        captured["args"] = args
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(build.subprocess, "run", fake_run)

    build.build(
        project_config={"build": "/tmp/build"},
        parallel="8",
        generator_options=["VERBOSE=1"],
        targets=["phlex/all", "phlex-examples/all"],
    )

    assert captured["args"] == [
        "cmake",
        "--build",
        "/tmp/build",
        "--target",
        "phlex/all",
        "phlex-examples/all",
        "--",
        "-j8",
        "VERBOSE=1",
    ]
