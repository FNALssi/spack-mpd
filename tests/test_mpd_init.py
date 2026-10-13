# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
from types import SimpleNamespace

import spack.paths
import spack.repo
from spack.extensions.mpd import init
from spack.main import SpackCommand

mpd = SpackCommand("mpd")


def test_initialize_mpd_indexes_all_repos(tmp_path, monkeypatch, capsys):
    index_calls = []
    output = []

    def record_index_call(name):
        index_calls.append(name)
        output.append(capsys.readouterr().out)

    repos = [
        SimpleNamespace(
            namespace=name,
            index=SimpleNamespace(_build_all_indexes=lambda name=name: record_index_call(name)),
        )
        for name in ("nova_spack", "sbn_spack", "a_very_long_repository_namespace")
    ]

    monkeypatch.setattr(spack.repo.PATH, "repos", repos)
    monkeypatch.setattr(init, "gray", lambda text: text)
    times = iter((100.0, 220.54, 300.0, 300.06, 400.0, 400.0))
    monkeypatch.setattr(init.time, "perf_counter", lambda: next(times))

    init.initialize_mpd(tmp_path / "mpd")

    assert index_calls == [repo.namespace for repo in repos]
    width = max(40, len(repos[-1].namespace) + 15)
    completions = ("done (120.5s)\n", "done (0.1s)\n", "done (0.0s)\n")
    for i, repo in enumerate(repos):
        prefix = f"      {repo.namespace} ".ljust(width, ".") + " "
        if i == 0:
            assert output[i].endswith(
                "Ensuring indexed recipe repositories (required by Spack):\n\n" + prefix
            )
        else:
            assert output[i] == completions[i - 1] + prefix
    assert capsys.readouterr().out == completions[-1] + "\n"


def test_mpd_init(tmp_mpd_dir):
    out = mpd("init")
    assert f"Initializing MPD for Spack instance at {spack.paths.prefix}" in out
    assert "MPD initialized" in out
    suites_dir = init.known_suites_dir(init.mpd_config_dir())
    assert suites_dir.exists()

    out = mpd("init")
    assert f"Warning: MPD already initialized for Spack instance at {spack.paths.prefix}" in out

    out = mpd("init", "-f", "-y")
    assert (
        "Warning: Reinitializing MPD for this Spack instance will remove all MPD projects" in out
    )
    assert f"Initializing MPD for Spack instance at {spack.paths.prefix}" in out
    assert "MPD initialized" in out
