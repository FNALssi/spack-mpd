# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import pytest

from spack.main import SpackCommand
import spack.paths

mpd = SpackCommand("mpd")


# Should replace this with a fixture
@pytest.fixture
def tmp_home_dir_with_cleanup(tmp_home_dir):
    try:
        yield
    finally:
        SpackCommand("repo")("rm", "local-mpd", fail_on_error=False)


def test_mpd_init(tmp_home_dir_with_cleanup):
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
