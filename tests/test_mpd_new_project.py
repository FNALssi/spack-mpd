# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import contextlib
import re

import spack.util.spack_yaml as syaml
from spack.extensions.mpd import concretize, config
from spack.extensions.mpd.spack_compat import fs
from spack.main import SpackCommand


# The default value of the top-level directory changes depending on the working
# directory.  For that reason, we cannot simply declare mpd to be an instance of
# SpackCommand("mpd") that can be used everywhere.
def mpd(*args):
    return SpackCommand("mpd")(*args)


@contextlib.contextmanager
def new_project(name=None, top=None, srcs=None, cwd=None, extra_args=None):
    arguments = []
    if name:
        arguments += ["--name", name]
    if top:
        arguments += ["-T", str(top)]
    if srcs:
        arguments += ["-S", str(srcs)]
    if extra_args:
        arguments += extra_args

    cm = contextlib.nullcontext()
    if cwd:
        cm = fs.working_dir(cwd, create=True)

    with cm:
        old_project = config.selected_project()
        new_project_name = None
        try:
            yield mpd("new-project", *arguments)
            new_project_name = config.selected_project_config()["name"]
        finally:
            if new_project_name:
                mpd("rm-project", "--force", new_project_name)
            if old_project:
                mpd("select", "-p", old_project)


def test_new_project_all_defaults(with_mpd_init, tmp_path):
    # Specify nothing
    cwd_z = tmp_path / "z"
    mpd("ls")
    with new_project(cwd=cwd_z) as out:
        assert "Creating project: z" in out
        assert f"top     {cwd_z}" in out
        assert f"build   {cwd_z}/build" in out
        assert f"local   {cwd_z}/local" in out
        assert f"sources {cwd_z}/srcs" in out
        assert "z" == config.selected_project()


def test_new_project_all_default_paths(with_mpd_init, tmp_path):
    # Specify only --name
    cwd_a = tmp_path / "a"
    mpd("ls")
    with new_project(name="a", cwd=cwd_a) as out:
        assert f"top     {cwd_a}" in out
        assert f"build   {cwd_a}/build" in out
        assert f"local   {cwd_a}/local" in out
        assert f"sources {cwd_a}/srcs" in out
        assert "a" == config.selected_project()

        out = mpd("status")
        assert re.search(r"Selected project:\s+a", out, re.DOTALL)
        assert "Development status: not concretized" in out


def test_new_project_only_top_path(with_mpd_init, tmp_path):
    # Specify --name and -T
    mpd("ls")
    top_level_b = tmp_path / "b"
    with new_project(name="b", top=top_level_b) as out:
        mpd("ls")
        assert f"top     {top_level_b}" in out
        assert f"build   {top_level_b}/build" in out
        assert f"local   {top_level_b}/local" in out
        assert f"sources {top_level_b}/srcs" in out


def test_new_project_only_srcs_path(with_mpd_init, tmp_path):
    # Specify --name and -S
    cwd_c = tmp_path / "c"
    srcs_c = tmp_path / "c_srcs"
    with new_project(name="c", srcs=srcs_c, cwd=cwd_c) as out:
        assert f"top     {cwd_c}" in out
        assert f"build   {cwd_c}/build" in out
        assert f"local   {cwd_c}/local" in out
        assert f"sources {srcs_c}" in out


def test_new_project_no_default_paths(with_mpd_init, tmp_path):
    # Specify --name, -T and -S
    top_level_d = tmp_path / "d"
    srcs_d = tmp_path / "d_srcs"
    with new_project(name="d", top=top_level_d, srcs=srcs_d) as out:
        assert f"top     {top_level_d}" in out
        assert f"build   {top_level_d}/build" in out
        assert f"local   {top_level_d}/local" in out
        assert f"sources {srcs_d}" in out


def test_mpd_refresh(with_mpd_init, tmp_path):
    with new_project(name="e", cwd=tmp_path):
        # Update the cached configuration
        mpd("ls")

        cfg = config.selected_project_config()
        out = mpd("refresh")
        new_cfg = config.selected_project_config()
        assert "Project e is up-to-date" in out
        assert cfg == new_cfg
        assert new_cfg["cxxstd"]["value"] == "17"

        out = mpd("refresh", "cxxstd=20")
        assert "Refreshing project: e" in out
        new_cfg = config.selected_project_config()
        assert new_cfg["cxxstd"]["value"] == "20"


def test_new_project_accepts_env_var_prepend(with_mpd_init, tmp_path):
    with new_project(
        name="test-env-arg",
        cwd=tmp_path,
        extra_args=["--env-var-prepend", "MY_ENVIRONMENT_VARIABLE=my_string"],
    ) as out:
        assert "Creating project: test-env-arg" in out
        project_cfg = config.selected_project_config()
        assert project_cfg["env_var_prepend"] == ["MY_ENVIRONMENT_VARIABLE=my_string"]


def test_refresh_accepts_env_var_prepend(with_mpd_init, tmp_path):
    with new_project(name="refresh-env-arg", cwd=tmp_path):
        out = mpd("refresh", "--env-var-prepend", "MY_ENVIRONMENT_VARIABLE=my_string")
        assert "Refreshing project: refresh-env-arg" in out
        project_cfg = config.selected_project_config()
        assert project_cfg["env_var_prepend"] == ["MY_ENVIRONMENT_VARIABLE=my_string"]


def test_add_env_var_prepend_paths(tmp_path):
    local_dir = tmp_path / "local"
    local_dir.mkdir()
    env_yaml = local_dir / "spack.yaml"

    with open(env_yaml, "w") as f:
        syaml.dump(
            {"spack": {"env_vars": {"prepend_path": {"PATH": "/tmp/compilers"}}}},
            stream=f,
            default_flow_style=False,
        )

    build_dir = tmp_path / "build"
    project_config = {
        "local": str(local_dir),
        "build": str(build_dir),
        "srcs": {"pkg2": "pkg2", "pkg1": "pkg1"},
        "env_var_prepend": ["MY_ENVIRONMENT_VARIABLE=my_string"],
    }

    concretize._add_env_var_prepend_paths(project_config)

    with open(env_yaml, "r") as f:
        loaded = syaml.load(f)

    expected = ":".join(
        [str(build_dir / "pkg1" / "my_string"), str(build_dir / "pkg2" / "my_string")]
    )
    prepend_path = loaded["spack"]["env_vars"]["prepend_path"]
    assert prepend_path["PATH"] == "/tmp/compilers"
    assert prepend_path["MY_ENVIRONMENT_VARIABLE"] == expected


def test_parse_dependency_spec_preserves_dependency_constraints_spacing():
    pkg_name, constraints = config.parse_dependency_spec(
        "py-llvmlite ^llvm libcxx=none libunwind=none"
    )

    assert pkg_name == "py-llvmlite"
    assert constraints == ["^llvm libcxx=none libunwind=none"]


def test_categorize_constraints_parses_dependency_name_with_space_separated_constraints():
    constraint_map = config.categorize_constraints(["^llvm libcxx=none libunwind=none"])

    assert "llvm" in constraint_map
    assert constraint_map["llvm"] == {
        "value": "llvm",
        "variant": "^llvm libcxx=none libunwind=none",
    }
