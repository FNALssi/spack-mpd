# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import spack.paths
from spack.main import SpackCommand

mpd = SpackCommand("mpd")


def test_mpd_init(tmp_mpd_dir):
    out = mpd("init")
    assert f"MPD initialized for Spack instance at {spack.paths.prefix}" in out

    out = mpd("init")
    assert f"Warning: MPD already initialized for Spack instance at {spack.paths.prefix}" in out

    out = mpd("init", "-f", "-y")
    assert "Warning: Reinitializing MPD on this system will remove all MPD projects" in out
    assert f"MPD initialized for Spack instance at {spack.paths.prefix}" in out
