# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import pytest

import spack.util.git
import spack.util.spack_yaml as syaml
from spack.extensions.mpd import clone, init
from spack.extensions.mpd.spack_compat import fs
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


def test_github_ssh_url_rewrite():
    assert (
        clone._github_ssh_url("https://github.com/FNALssi/cetlib.git")
        == "git@github.com:FNALssi/cetlib.git"
    )
    assert clone._github_ssh_url("https://gitlab.com/FNALssi/cetlib.git") is None
    assert clone._github_ssh_url("git@github.com:FNALssi/cetlib.git") is None


def test_clone_repos_reports_https_fallback(monkeypatch, tmp_path, capsys):
    repo = clone.GitHubRepo("FNALssi", "cetlib")

    def fake_clone(_repo, _srcs_area, prefer_ssh=False, branch=None, tag=None):
        assert prefer_ssh is True
        return (None, True)

    monkeypatch.setattr(clone, "_clone", fake_clone)

    changed = clone.clone_repos(
        {"cetlib": repo},
        should_fork=False,
        srcs_area=str(tmp_path),
        local_area=str(tmp_path),
        prefer_ssh=True,
    )

    assert changed is True
    out = capsys.readouterr().out
    assert "cloned via https fallback" in out


@pytest.mark.parametrize("option", ["branch", "tag"])
def test_clone_passes_ref_to_git(monkeypatch, tmp_path, option):
    repo = clone.GitHubRepo("FNALssi", "cetlib")
    calls = []

    class FakeGit:
        returncode = 0

        def add_default_arg(self, *args):
            calls.append(("default",) + args)

        def __call__(self, *args, **kwargs):
            calls.append(args)
            return "Cloning into cetlib"

    monkeypatch.setattr(clone.spack.util.git, "git", lambda required: FakeGit())

    kwargs = {option: "v1.2.3" if option == "tag" else "feature/test"}
    result, fallback = clone._clone(repo, str(tmp_path), **kwargs)

    assert result is None
    assert fallback is False
    assert calls[-1] == ("clone", "--branch", kwargs[option], repo.url(), str(tmp_path / "cetlib"))


def test_clone_skips_existing_destination(monkeypatch, tmp_path, capsys):
    repo = clone.GitHubRepo("FNALssi", "cetlib")
    (tmp_path / "cetlib").mkdir()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("git clone should not run for an existing destination")

    monkeypatch.setattr(clone.spack.util.git, "git", fail_if_called)
    changed = clone.clone_repos(
        {"cetlib": repo},
        should_fork=False,
        srcs_area=str(tmp_path),
        local_area=str(tmp_path),
        branch="feature/test",
    )

    assert changed is False
    assert "already cloned" in capsys.readouterr().out


def test_branch_and_tag_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        mpd("g", "--branch", "main", "--tag", "v1.0", "cetlib")
