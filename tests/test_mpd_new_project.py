# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import pathlib
import pytest
from contextlib import contextmanager

from spack.main import SpackCommand, SpackCommandError
import llnl.util.filesystem as fs


# The default value of the top-level directory changes depending on
# the working directory.  For that reason, we cannot simply declare
# mpd to be an instance of SpackCommand("mpd") that can be used
# everywhere.
def mpd(*args):
    return SpackCommand("mpd")(*args)


# Should replace this with a fixture
@contextmanager
def cleanup(project):
    try:
        yield
    finally:
        mpd("rm", "-f", project)


def test_new_project_paths(tmpdir):
    # Specify neither -T or -S
    top_level_a = tmpdir / "a"
    with fs.working_dir(top_level_a, create=True), cleanup("a"):
        out = mpd("new-project", "--name", "a")
        assert f"build area: {top_level_a}/build" in out
        assert f"local area: {top_level_a}/local" in out
        assert f"sources area: {top_level_a}/srcs" in out

    # Specify only -T
    with cleanup("b"):
        top_level_b = tmpdir / "b"
        out = mpd("new-project", "--name", "b", "-T", str(top_level_b))
        assert f"build area: {top_level_b}/build" in out
        assert f"local area: {top_level_b}/local" in out
        assert f"sources area: {top_level_b}/srcs" in out

    # Specify only -S
    top_level_c = tmpdir / "c"
    with fs.working_dir(top_level_c, create=True), cleanup("c"):
        srcs_c = tmpdir / "c_srcs"
        out = mpd("new-project", "--name", "c", "-S", str(srcs_c))
        assert f"build area: {top_level_c}/build" in out
        assert f"local area: {top_level_c}/local" in out
        assert f"sources area: {srcs_c}" in out

    # Specify both -T and -S
    with cleanup("d"):
        top_level_d = tmpdir / "d"
        srcs_d = tmpdir / "d_srcs"
        out = mpd("new-project", "--name", "d", "-T", str(top_level_d), "-S", str(srcs_d))
        assert f"build area: {top_level_d}/build" in out
        assert f"local area: {top_level_d}/local" in out
        assert f"sources area: {srcs_d}" in out


def test_mpd_refresh(tmpdir):
    pass
