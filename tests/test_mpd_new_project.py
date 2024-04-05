# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import pytest
from contextlib import contextmanager

from spack.main import SpackCommand
import llnl.util.filesystem as fs


# The default value of the top-level directory changes depending on
# the working directory.  For that reason, we cannot simply declare
# mpd to be an instance of SpackCommand("mpd") that can be used
# everywhere.
def mpd(*args):
    return SpackCommand("mpd")(*args)


# Should replace this with a fixture
@contextmanager
def project(name, cwd=None):
    if cwd is None:
        try:
            yield
        finally:
            mpd("rm", "-f", name)
        return

    # Temporary working directory
    with fs.working_dir(cwd, create=True):
        try:
            yield
        finally:
            mpd("rm", "-f", name)


def test_new_project_paths(with_mpd_init, tmp_path):
    # Specify neither -T or -S
    cwd_a = tmp_path / "a"
    with project("a", cwd=cwd_a):
        out = mpd("new-project", "--name", "a")
        assert f"build area: {cwd_a}/build" in out
        assert f"local area: {cwd_a}/local" in out
        assert f"sources area: {cwd_a}/srcs" in out

    # Specify only -T
    top_level_b = tmp_path / "b"
    with project("b"):
        out = mpd("new-project", "--name", "b", "-T", str(top_level_b))
        assert f"build area: {top_level_b}/build" in out
        assert f"local area: {top_level_b}/local" in out
        assert f"sources area: {top_level_b}/srcs" in out

    # Specify only -S
    cwd_c = tmp_path / "c"
    srcs_c = tmp_path / "c_srcs"
    with project("c", cwd=cwd_c):
        out = mpd("new-project", "--name", "c", "-S", str(srcs_c))
        assert f"build area: {cwd_c}/build" in out
        assert f"local area: {cwd_c}/local" in out
        assert f"sources area: {srcs_c}" in out

    # Specify both -T and -S
    top_level_d = tmp_path / "d"
    srcs_d = tmp_path / "d_srcs"
    with project("d"):
        out = mpd("new-project", "--name", "d", "-T", str(top_level_d), "-S", str(srcs_d))
        assert f"build area: {top_level_d}/build" in out
        assert f"local area: {top_level_d}/local" in out
        assert f"sources area: {srcs_d}" in out


def test_mpd_refresh(tmp_path):
    pass
