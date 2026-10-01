# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import contextlib
import re
from types import SimpleNamespace

import pytest

import spack.cmd
import spack.util.spack_yaml as syaml
from spack.extensions.mpd import concretize, config
from spack.extensions.mpd.spack_compat import fs
from spack.main import SpackCommand, SpackCommandError
from spack.spec import Spec


# The default value of the top-level directory changes depending on the working
# directory.  For that reason, we cannot simply declare mpd to be an instance of
# SpackCommand("mpd") that can be used everywhere.
def mpd(*args):
    return SpackCommand("mpd")(*args)


class _FakeSpec:
    def __init__(self, name, dag_hash, cshort_spec):
        self.name = name
        self._dag_hash = dag_hash
        self.cshort_spec = cshort_spec

    def dag_hash(self):
        return self._dag_hash


class _FakeEnvironment:
    def __init__(self, specs):
        self._specs = specs

    def all_specs(self):
        return self._specs


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


def test_new_project_top_dot_uses_current_directory_name(with_mpd_init, tmp_path):
    project_dir = tmp_path / "dot-project"

    with new_project(top=".", cwd=project_dir) as out:
        assert "Creating project: dot-project" in out
        assert config.selected_project() == "dot-project"
        assert config.selected_project_config()["name"] == "dot-project"

        status = mpd("status")
        assert re.search(r"Selected project:\s+dot-project", status, re.DOTALL)


def test_new_project_top_dot_slash_uses_current_directory_name(with_mpd_init, tmp_path):
    project_dir = tmp_path / "slash-project"

    with new_project(top="./", cwd=project_dir):
        assert config.selected_project() == "slash-project"


def test_new_project_relative_top_uses_resolved_directory_name(with_mpd_init, tmp_path):
    working_dir = tmp_path / "working-dir"
    project_dir = tmp_path / "relative-project"

    with new_project(top="../relative-project", cwd=working_dir):
        assert config.selected_project() == "relative-project"
        assert config.selected_project_config()["top"] == str(project_dir)


def test_new_project_explicit_name_overrides_top_directory_name(with_mpd_init, tmp_path):
    project_dir = tmp_path / "directory-name"

    with new_project(name="explicit-name", top=".", cwd=project_dir):
        assert config.selected_project() == "explicit-name"


def test_new_project_root_top_requires_name(with_mpd_init):
    with pytest.raises(SpackCommandError):
        mpd("new-project", "--top", "/")


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


def test_new_project_rejects_collision_before_creating_directories(
    with_mpd_init, tmp_path, monkeypatch
):
    existing_top = tmp_path / "existing"
    config.update(
        {
            "name": "existing",
            "top": str(existing_top),
            "source": str(tmp_path / "shared"),
            "build": str(existing_top / "build"),
            "local": str(existing_top / "local"),
            "packages": {},
        }
    )
    candidate_top = existing_top / "nested"
    monkeypatch.setattr(config, "select_compiler", lambda _: pytest.fail("compiler selected"))

    command = SpackCommand("mpd")
    output = command(
        "new-project",
        "--name",
        "candidate",
        "--top",
        str(candidate_top),
        fail_on_error=False,
    )

    assert command.returncode == 1
    assert "Unsafe MPD project path conflicts" in output
    assert not candidate_top.exists()
    assert config.selected_project() is None


def test_new_project_allows_external_shared_source(with_mpd_init, tmp_path):
    shared = tmp_path / "shared"
    first_top = tmp_path / "first"
    second_top = tmp_path / "second"
    with new_project(name="first", top=first_top, srcs=shared):
        with new_project(name="second", top=second_top, srcs=shared):
            assert config.shared_source_peers("first") == ("second",)


def test_new_project_rejects_sharing_source_inside_project_top(with_mpd_init, tmp_path):
    first_top = tmp_path / "first"
    shared = first_top / "srcs"
    with new_project(name="first", top=first_top):
        command = SpackCommand("mpd")
        output = command(
            "new-project",
            "--name",
            "second",
            "--top",
            str(tmp_path / "second"),
            "--srcs",
            str(shared),
            fail_on_error=False,
        )
        assert command.returncode == 1
        assert "Unsafe MPD project path conflicts" in output


def test_new_project_rejects_top_around_existing_shared_source(with_mpd_init, tmp_path):
    shared = tmp_path / "shared"
    first = {
        "name": "first",
        "top": str(tmp_path / "first"),
        "source": str(shared),
        "build": str(tmp_path / "first" / "build"),
        "local": str(tmp_path / "first" / "local"),
    }
    second = {
        "name": "second",
        "top": str(tmp_path / "second"),
        "source": str(shared),
        "build": str(tmp_path / "second" / "build"),
        "local": str(tmp_path / "second" / "local"),
    }
    config.update(first)
    config.update(second)

    command = SpackCommand("mpd")
    output = command(
        "new-project",
        "--name",
        "third",
        "--top",
        str(tmp_path),
        "--srcs",
        str(tmp_path / "third-source"),
        fail_on_error=False,
    )

    assert command.returncode == 1
    assert "Unsafe MPD project path conflicts" in output
    assert not (tmp_path / "build").exists()


def test_new_project_force_rejects_replacement_with_different_paths(with_mpd_init, tmp_path):
    top = tmp_path / "original"
    project = {
        "name": "existing",
        "top": str(top),
        "source": str(top / "srcs"),
        "build": str(top / "build"),
        "local": str(top / "local"),
    }
    config.update(project)
    replacement = tmp_path / "replacement"

    command = SpackCommand("mpd")
    output = command(
        "new-project",
        "--name",
        "existing",
        "--top",
        str(replacement),
        "--force",
        fail_on_error=False,
    )

    assert command.returncode == 1
    assert "Cannot replace MPD project existing using different directories" in output
    assert f"top: {top} -> {replacement}" in output
    assert "does not move its build files or Spack environment" in output
    assert "Run 'spack mpd rm-project --force existing'" in output
    assert not replacement.exists()


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


def test_new_project_require_reuse_requires_env(with_mpd_init, tmp_path):
    command = SpackCommand("mpd")
    out = command(
        "new-project",
        "--name",
        "require-reuse",
        "-T",
        str(tmp_path),
        "--require-reuse",
        fail_on_error=False,
    )

    assert command.returncode == 1
    assert "--require-reuse requires -E/--env" in out


def test_new_project_persists_require_reuse(with_mpd_init, tmp_path):
    with new_project(
        name="require-reuse",
        cwd=tmp_path,
        extra_args=["-E", "test-environment", "--require-reuse"],
    ):
        assert config.selected_project_config()["require_reuse"] is True


def test_verify_required_reuse_accepts_matching_specs(monkeypatch):
    # Test the post-concretization reuse check directly; no Spack concretization is performed here.
    shared_spec = _FakeSpec("dependency", "abc123", "dependency@1.0/abc123")
    monkeypatch.setattr(concretize.ev, "read", lambda _: _FakeEnvironment([shared_spec]))

    concretize.verify_required_reuse(
        _FakeEnvironment([shared_spec]), packages={}, ignored_packages=[], proto_env="source-env"
    )


def test_verify_required_reuse_reports_missing_specs(monkeypatch, capsys):
    # Test the post-concretization reuse check directly; no Spack concretization is performed here.
    missing_spec = _FakeSpec("dependency", "abc123", "dependency@1.0/abc123")
    monkeypatch.setattr(concretize.ev, "read", lambda _: _FakeEnvironment([]))

    with pytest.raises(SystemExit):
        concretize.verify_required_reuse(
            _FakeEnvironment([missing_spec]),
            packages={},
            ignored_packages=[],
            proto_env="source-env",
        )
    assert "dependency@1.0/abc123" in capsys.readouterr().err


@pytest.mark.parametrize(
    "from_items",
    [[{"type": "local"}, {"type": "external"}], [{"type": "environment", "path": "source-env"}]],
)
def test_create_initial_environment_does_not_reuse_roots(monkeypatch, tmp_path, from_items):
    captured = {}
    expected_env = object()

    def capture_yaml(_, contents, prefix):
        captured["contents"] = contents
        captured["prefix"] = prefix
        return tmp_path / "initial.yaml"

    monkeypatch.setattr(concretize, "make_yaml_file", capture_yaml)
    monkeypatch.setattr(concretize, "_run", lambda _: None)
    monkeypatch.setattr(concretize, "update", lambda *args, **kwargs: None)
    monkeypatch.setattr(concretize.ev, "exists", lambda _: False)
    monkeypatch.setattr(concretize.ev, "create", lambda *args, **kwargs: None)
    monkeypatch.setattr(concretize.ev, "read", lambda _: expected_env)

    result = concretize.create_initial_environment(
        {"name": "test", "local": str(tmp_path)}, {"developed": {}}, {}, from_items, []
    )

    assert result is expected_env
    assert captured["contents"]["spack"]["concretizer"]["reuse"] == {
        "roots": False,
        "from": from_items,
    }


def test_dependency_only_constraint_preserves_only_required_configuration(monkeypatch):
    selected = Spec(
        "dependency@=1.2+required+selected+defaulted patches:=abc "
        "platform=linux os=ubuntu22.04 target=x86_64 %cxx=gcc@=10 ^transitive@=3"
    )
    variant_defaults = {"required": False, "selected": False, "defaulted": True}
    package = SimpleNamespace(
        has_variant=lambda name: name in variant_defaults,
        get_variant=lambda name: SimpleNamespace(default=variant_defaults[name]),
    )
    monkeypatch.setattr(type(selected), "package", property(lambda _: package))
    recipe_dependency = SimpleNamespace(spec=Spec("dependency@1:+required"))

    constraint = concretize._dependency_only_constraint(selected, [recipe_dependency])

    assert str(constraint) == "dependency@=1.2+required+selected"
    assert selected.satisfies(constraint)
    assert constraint.architecture is None
    assert not constraint.dependencies(virtuals=("c", "cxx", "fortran"))
    assert "patches" not in constraint.variants
    assert "defaulted" not in constraint.variants
    assert not constraint.edges_to_dependencies()
    assert constraint.abstract_hash is None


def test_collect_first_order_dependencies_merges_origins(monkeypatch):
    dependency = Spec("dependency@=2.0+shared")
    dependency.external_path = None
    edge = SimpleNamespace(
        spec=dependency, virtuals=(), depflag=concretize.dt.LINK | concretize.dt.RUN
    )
    injected_edges = []
    for name in ("compiler-wrapper", "gcc-runtime"):
        spec = Spec(name)
        spec.external_path = None
        injected_edges.append(SimpleNamespace(spec=spec, virtuals=(), depflag=concretize.dt.BUILD))
    parents = [SimpleNamespace(name=name) for name in ("developed-a", "developed-b")]
    recipe_dependency = SimpleNamespace(
        spec=Spec("dependency@2:"), depflag=concretize.dt.LINK | concretize.dt.RUN
    )

    class Environment:
        def concretized_specs(self):
            return [(parent.name, parent) for parent in parents]

    original_traverse_edges = concretize.traverse.traverse_edges

    def traverse_edges(roots, *args, **kwargs):
        if roots and any(roots[0] is parent for parent in parents):
            return [(1, injected) for injected in injected_edges] + [(1, edge)]
        return original_traverse_edges(roots, *args, **kwargs)

    monkeypatch.setattr(concretize.traverse, "traverse_edges", traverse_edges)
    monkeypatch.setattr(
        concretize, "_active_recipe_dependencies", lambda parent, selected: [recipe_dependency]
    )
    monkeypatch.setattr(
        concretize,
        "_dependency_only_constraint",
        lambda selected, dependencies: Spec("dependency@=2.0+shared"),
    )
    monkeypatch.setattr(spack.cmd, "parse_specs", lambda _: [Spec("gcc@=12")])

    promoted, supplemental, cetmodules4 = concretize.collect_first_order_dependencies(
        Environment(), {parent.name: {} for parent in parents}, {"compiler": {"value": "gcc@=12"}}
    )

    assert len(promoted) == 1
    assert promoted[0].constraint.satisfies("dependency@=2.0+shared")
    assert [origin.developed_package for origin in promoted[0].origins] == [
        "developed-a",
        "developed-b",
    ]
    assert all(
        origin.recipe_constraint.satisfies("dependency@2:") for origin in promoted[0].origins
    )
    assert all(origin.deptypes == frozenset({"link", "run"}) for origin in promoted[0].origins)
    assert supplemental == {"cmake"}
    assert cetmodules4 is True


def test_verify_promoted_dependencies_accepts_satisfying_root():
    root = Spec("dependency@1.2+shared")
    promoted = concretize.PromotedDependency(
        Spec("dependency@1.2+shared"),
        (
            concretize.DependencyOrigin(
                "developed", Spec("dependency@1:"), frozenset({"link", "run"})
            ),
        ),
    )

    class Environment:
        def concrete_roots(self):
            return [root]

    concretize.verify_promoted_dependencies(Environment(), (promoted,))


def test_verify_promoted_dependencies_reports_recipe_violation(capsys):
    root = Spec("dependency@1.2")
    promoted = concretize.PromotedDependency(
        Spec("dependency@1.2"),
        (concretize.DependencyOrigin("developed", Spec("dependency@2:"), frozenset({"link"})),),
    )

    class Environment:
        def concrete_roots(self):
            return [root]

    with pytest.raises(SystemExit):
        concretize.verify_promoted_dependencies(Environment(), (promoted,))

    error = capsys.readouterr().err
    assert "developed package: developed" in error
    assert "dependency types: link" in error
    assert "recipe constraint: dependency@2:" in error
    assert "result: dependency@1.2" in error


def test_finalize_environment_verifies_both_concretizations(monkeypatch, tmp_path):
    commands = []
    root_reuse = []
    environments = [object(), object()]
    verified = []
    promoted = concretize.PromotedDependency(
        Spec("dependency@1.2"),
        (concretize.DependencyOrigin("developed", Spec("dependency@1:"), frozenset()),),
    )

    monkeypatch.setattr(concretize, "_run", lambda command: commands.append(command))
    monkeypatch.setattr(
        concretize, "enable_dependency_root_reuse", lambda path: root_reuse.append(path)
    )
    monkeypatch.setattr(concretize.ev, "Environment", lambda _: environments.pop(0))
    monkeypatch.setattr(
        concretize,
        "verify_promoted_dependencies",
        lambda env, dependencies: verified.append((env, dependencies)),
    )
    monkeypatch.setattr(concretize, "update", lambda *args, **kwargs: None)

    result = concretize.finalize_environment(
        {"local": str(tmp_path)}, {"developed": {}}, (promoted,), {"cmake"}
    )

    assert commands == [
        ["spack", "-D", str(tmp_path), "add", "cmake", "dependency@1.2"],
        ["spack", "-D", str(tmp_path), "concretize"],
        ["spack", "-D", str(tmp_path), "rm", "developed"],
        ["spack", "-D", str(tmp_path), "concretize"],
    ]
    assert root_reuse == [str(tmp_path)]
    assert len(verified) == 2
    assert verified[0][1] == (promoted,)
    assert verified[1][1] == (promoted,)
    assert result is verified[1][0]


def test_finalize_environment_omits_duplicate_supplemental_root(monkeypatch, tmp_path):
    commands = []
    promoted = concretize.PromotedDependency(
        Spec("cmake@=3.31"),
        (concretize.DependencyOrigin("developed", Spec("cmake@3.24:"), frozenset()),),
    )

    monkeypatch.setattr(concretize, "_run", lambda command: commands.append(command))
    monkeypatch.setattr(concretize, "enable_dependency_root_reuse", lambda path: None)
    monkeypatch.setattr(concretize.ev, "Environment", lambda _: object())
    monkeypatch.setattr(concretize, "verify_promoted_dependencies", lambda *args: None)
    monkeypatch.setattr(concretize, "update", lambda *args, **kwargs: None)

    concretize.finalize_environment(
        {"local": str(tmp_path)}, {"developed": {}}, (promoted,), {"cmake"}
    )

    assert commands[0] == ["spack", "-D", str(tmp_path), "add", "cmake@=3.31"]


def test_enable_dependency_root_reuse_preserves_sources(tmp_path):
    env_yaml = tmp_path / "spack.yaml"
    reuse_sources = [{"type": "local"}, {"type": "external"}]
    with open(env_yaml, "w") as f:
        syaml.dump(
            {
                "spack": {
                    "specs": ["developed"],
                    "concretizer": {
                        "unify": True,
                        "reuse": {"roots": False, "from": reuse_sources},
                    },
                }
            },
            stream=f,
            default_flow_style=False,
        )

    concretize.enable_dependency_root_reuse(tmp_path)

    with open(env_yaml, "r") as f:
        config = syaml.load(f)
    assert config["spack"]["concretizer"]["reuse"] == {"roots": True, "from": reuse_sources}


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


def test_format_compiler_help_message_empty_compiler_list():
    msg = config._format_compiler_help_message([])

    assert msg == (
        "No compilers are configured in this Spack instance. "
        "Configure one manually or run `spack compiler find`."
    )


def test_format_compiler_help_message_lists_known_compilers_sorted_and_unique():
    class FakeCompiler:
        def __init__(self, spec):
            self.spec = spec

        def __str__(self):
            return self.spec

    msg = config._format_compiler_help_message(
        [FakeCompiler("gcc@12.2.0"), FakeCompiler("clang@16.0.0"), FakeCompiler("gcc@12.2.0")]
    )

    assert msg == "Available compilers:\n  clang@16.0.0\n  gcc@12.2.0"
