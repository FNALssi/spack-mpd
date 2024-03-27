# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import pytest
import subprocess

from spack.main import SpackCommand, SpackCommandError

mpd = SpackCommand("mpd")


def test_new_project_clone(tmpdir):
    top_level_clone = tmpdir / "test-clone"
    top_level_clone.mkdir()
    subprocess.run(
        ["spack", "mpd", "new-project", "--name", "test-clone"],
        capture_output=True,
        text=True,
        cwd=top_level_clone,
    )
    mpd("g", "cetlib")
    assert (top_level_clone / "srcs" / "cetlib").exists()
    mpd("rm", "test-clone")
