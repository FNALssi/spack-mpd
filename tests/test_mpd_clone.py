# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
from spack.main import SpackCommand
import llnl.util.filesystem as fs

mpd = SpackCommand("mpd")


def test_new_project_clone(with_mpd_init, tmp_path):
    with fs.working_dir(tmp_path):
        mpd("new-project", "--name", "test-clone")
        mpd("g", "cetlib")
        assert (tmp_path / "srcs" / "cetlib").exists()
        mpd("rm", "-f", "test-clone")
