# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import spack.llnl.util.filesystem as fs
import spack.util.spack_yaml as syaml
from spack.extensions.mpd import clone, init
from spack.main import SpackCommand

mpd = SpackCommand("mpd")


def test_new_project_clone(with_mpd_init, tmp_path):
    with fs.working_dir(tmp_path):
        mpd("new-project", "--name", "test-clone")
        mpd("g", "cetlib")
        assert (tmp_path / "srcs" / "cetlib").exists()
        mpd("rm", "-f", "test-clone")


def test_add_suite_file(with_mpd_init, tmp_path):
    suite_path = tmp_path / "custom-suite.yaml"
    with open(suite_path, "w") as f:
        syaml.dump({"custom": {"gh_org_name": "FNALssi", "repos": ["cetlib"]}}, stream=f)

    out = mpd("g", "--add-suite", str(suite_path))
    assert "Added suite" in out

    known_suite = init.known_suites_dir(init.mpd_config_dir()) / "custom-suite.yaml"
    assert known_suite.exists()
    assert clone.suite_for("custom").repos == ["cetlib"]


def test_add_suite_file_can_abort_overwrite(with_mpd_init, tmp_path, monkeypatch):
    suite_path = tmp_path / "critic-suite.yaml"
    with open(suite_path, "w") as f:
        syaml.dump(
            {"critic": {"gh_org_name": "alternate-org", "repos": ["replacement"]}}, stream=f
        )

    monkeypatch.setattr(clone.tty, "get_yes_or_no", lambda *args, **kwargs: False)
    assert clone._add_suite_file(str(suite_path)) is False

    existing = clone.suite_for("critic")
    assert "replacement" not in existing.repos


def test_remove_suite_file(with_mpd_init, tmp_path, monkeypatch):
    suite_path = tmp_path / "custom-remove-suite.yaml"
    with open(suite_path, "w") as f:
        syaml.dump({"custom-remove": {"gh_org_name": "FNALssi", "repos": ["cetlib"]}}, stream=f)

    mpd("g", "--add-suite", str(suite_path))
    assert clone.suite_for("custom-remove").repos == ["cetlib"]

    monkeypatch.setattr(clone.tty, "get_yes_or_no", lambda *args, **kwargs: True)
    out = mpd("g", "--remove-suite", "custom-remove")
    assert "Removed suite" in out

    known_suite = init.known_suites_dir(init.mpd_config_dir()) / "custom-remove-suite.yaml"
    assert not known_suite.exists()


def test_remove_suite_can_abort(with_mpd_init, tmp_path, monkeypatch):
    suite_path = tmp_path / "custom-keep-suite.yaml"
    with open(suite_path, "w") as f:
        syaml.dump({"custom-keep": {"gh_org_name": "FNALssi", "repos": ["cetlib"]}}, stream=f)

    mpd("g", "--add-suite", str(suite_path))
    monkeypatch.setattr(clone.tty, "get_yes_or_no", lambda *args, **kwargs: False)

    out = mpd("g", "--remove-suite", "custom-keep")
    assert "Skipped removing suite" in out

    known_suite = init.known_suites_dir(init.mpd_config_dir()) / "custom-keep-suite.yaml"
    assert known_suite.exists()


def test_remove_suite_errors_for_unknown_suite(with_mpd_init):
    out = mpd("g", "--remove-suite", "no-such-suite", fail_on_error=False)
    assert "Cannot remove unknown suite" in out
