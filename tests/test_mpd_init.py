# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
from contextlib import contextmanager
from pathlib import Path
import pytest

from spack.main import SpackCommand, SpackCommandError
import spack.paths
from spack.extensions.mpd import config

mpd = SpackCommand("mpd")


# Should replace this with a fixture
@contextmanager
def cleanup_repo(path):
    try:
        yield
    finally:
        SpackCommand("repo")("rm", str(config.user_config_dir()))


def test_mpd_init(monkeypatch, tmpdir):
    path = Path(tmpdir)
    with monkeypatch.context() as m, cleanup_repo(path):
        m.setattr(Path, "home", lambda: path)
        out = mpd("init")
        assert f"Using Spack instance at {spack.paths.prefix}" in out
        assert "Added repo with namespace 'local-mpd'" in out

        out = mpd("init")
        assert f"Using Spack instance at {spack.paths.prefix}" in out
        assert "Warning: MPD already initialized on this system" in out

        out = mpd("init", "-f", "-y")
        assert "Warning: Reinitializing MPD on this system will remove all MPD projects" in out
        assert f"Using Spack instance at {spack.paths.prefix}" in out
        assert "Added repo with namespace 'local-mpd'" in out
