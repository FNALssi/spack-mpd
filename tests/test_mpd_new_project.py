# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import contextlib

import llnl.util.filesystem as fs

from spack.extensions.mpd import config
from spack.main import SpackCommand


# The default value of the top-level directory changes depending on the working
# directory.  For that reason, we cannot simply declare mpd to be an instance of
# SpackCommand("mpd") that can be used everywhere.
def mpd(*args):
    return SpackCommand("mpd")(*args)


@contextlib.contextmanager
def new_project(name, top=None, srcs=None, cwd=None):
    arguments = ["--name", name]
    if top:
        arguments += ["-T", str(top)]
    if srcs:
        arguments += ["-S", str(srcs)]

    cm = contextlib.nullcontext()
    if cwd:
        cm = fs.working_dir(cwd, create=True)

    with cm:
        old_project = config.selected_project()
        try:
            yield mpd("new-project", *arguments)
        finally:
            mpd("rm-project", "--force", name)
            if old_project:
                mpd("select", old_project)


def test_new_project_all_default_paths(with_mpd_init, tmp_path):
    # Specify neither -T or -S
    cwd_a = tmp_path / "a"
    mpd("ls")
    with new_project(name="a", cwd=cwd_a) as out:
        print(out)
        assert f"build area: {cwd_a}/build" in out
        assert f"local area: {cwd_a}/local" in out
        assert f"sources area: {cwd_a}/srcs" in out
        assert "a" == config.selected_project()

        out = mpd("status")
        assert "Selected project: a" in out
        assert "Environment status: inactive" in out


def test_new_project_only_top_path(with_mpd_init, tmp_path):
    # Specify only -T
    mpd("ls")
    top_level_b = tmp_path / "b"
    with new_project(name="b", top=top_level_b) as out:
        mpd("ls")
        assert f"build area: {top_level_b}/build" in out
        assert f"local area: {top_level_b}/local" in out
        assert f"sources area: {top_level_b}/srcs" in out


def test_new_project_only_srcs_path(with_mpd_init, tmp_path):
    # Specify only -S
    cwd_c = tmp_path / "c"
    srcs_c = tmp_path / "c_srcs"
    with new_project(name="c", srcs=srcs_c, cwd=cwd_c) as out:
        assert f"build area: {cwd_c}/build" in out
        assert f"local area: {cwd_c}/local" in out
        assert f"sources area: {srcs_c}" in out


def test_new_project_no_default_paths(with_mpd_init, tmp_path):
    # Specify both -T and -S
    top_level_d = tmp_path / "d"
    srcs_d = tmp_path / "d_srcs"
    with new_project(name="d", top=top_level_d, srcs=srcs_d) as out:
        assert f"build area: {top_level_d}/build" in out
        assert f"local area: {top_level_d}/local" in out
        assert f"sources area: {srcs_d}" in out


def test_mpd_refresh(with_mpd_init, tmp_path):
    with new_project(name="e", cwd=tmp_path):
        cfg = config.selected_project_config()
        out = mpd("refresh")
        new_cfg = config.selected_project_config()
        assert "Project e is up-to-date" in out
        assert cfg == new_cfg
        print(new_cfg)
        assert new_cfg["cxxstd"] == "cxxstd=17"

        out = mpd("refresh", "cxxstd=20")
        assert "Refreshing project: e" in out
        new_cfg = config.selected_project_config()
        assert new_cfg["cxxstd"] == "cxxstd=20"
