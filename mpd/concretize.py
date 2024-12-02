import copy
import functools
import json
import os
import re
import shutil
import subprocess
import time
from collections import abc
from pathlib import Path

from ruamel.yaml.scalarstring import SingleQuotedScalarString as YamlQuote

import llnl.util.tty as tty

import spack.compilers as compilers
import spack.environment as ev
import spack.util.spack_yaml as syaml
from spack import traverse
from spack.spec import InstallStatus

from .config import update
from .util import bold, cyan, get_number, gray, make_yaml_file

SUBCOMMAND = "new-project"
ALIASES = ["n"]

CMAKE_CACHE_VARIABLE_PATTERN = re.compile(r"-D(.*):(.*)=(.*)")


def find_environment(env_str):
    # Patterned off of the behavior in spack.cmd.find_environment
    if ev.exists(env_str):
        return ev.read(env_str)
    if ev.is_env_dir(env_str):
        return ev.Environment(env_str)
    tty.die(f"{env_str} does not correspond to an environment.")


def cmake_package_variables(name, cmake_args):
    if not cmake_args:
        return ""

    def begin_set_macro(name):
        name_with_underscores = name.replace("-", "_")
        return f"macro(set_{name_with_underscores}_variables)\n"

    def begin_unset_macro(name):
        name_with_underscores = name.replace("-", "_")
        return f"macro(unset_{name_with_underscores}_variables)\n"

    def end():
        return "endmacro()\n"

    set_contents = ""
    unset_contents = ""
    for arg in cmake_args:
        match = CMAKE_CACHE_VARIABLE_PATTERN.match(arg)
        if match:
            variable, vartype, value = match.groups()
            set_contents += f"""  # Set {variable}
  if(DEFINED {variable})
    set(OLD_{variable} "${{{variable}}}")
  endif()
  set({variable} "{value}" CACHE {vartype} "" FORCE)
"""
            unset_contents += f"""  # Restore/unset {variable}
  if(DEFINED OLD_{variable})
    set({variable} "${{OLD_{variable}}}" CACHE {vartype} "" FORCE)
    unset(OLD_{variable})
  else()
    unset({variable} CACHE)
  endif()
"""
    return begin_set_macro(name) + set_contents + end() + "\n" + \
        begin_unset_macro(name) + unset_contents + end() + "\n"


def cmake_develop(project_config, package_cmake_args):
    project_name = project_config["name"]
    source_path = Path(project_config["source"])
    file_dir = Path(__file__).resolve().parent
    with open((source_path / "develop.cmake").absolute(), "w") as out:
        for name, args in package_cmake_args.items():
            out.write(f"# {name} variables\n" + cmake_package_variables(name, args))
        out.write(f"""set(CWD "{file_dir}")
macro(develop pkg)
  install(CODE "execute_process(COMMAND spack python ensure-install-directory.py\\
                                        {project_name} ${{${{pkg}}_HASH}}\\
                                WORKING_DIRECTORY ${{CWD}})")
  install(CODE "set(CMAKE_INSTALL_PREFIX ${{${{pkg}}_INSTALL_PREFIX}})")
  string(REPLACE "-" "_" pkg_with_underscores ${{pkg}})
  cmake_language(CALL "set_${{pkg_with_underscores}}_variables")
  add_subdirectory(${{pkg}})
  cmake_language(CALL "unset_${{pkg_with_underscores}}_variables")
  install(CODE "execute_process(COMMAND spack python add-to-database.py\\
                                        {project_name} ${{${{pkg}}_HASH}}\\
                                WORKING_DIRECTORY ${{CWD}})")
endmacro()
""")


def cmake_lists_preamble(project_name):
    date = time.strftime("%Y-%m-%d")
    return f"""cmake_minimum_required(VERSION 3.18.2 FATAL_ERROR)
enable_testing()

project({project_name}-{date} LANGUAGES NONE)

include(develop.cmake)
"""


def cmake_lists(project_config, dependencies):
    source_path = Path(project_config["source"])
    with open((source_path / "CMakeLists.txt").absolute(), "w") as f:
        f.write(cmake_lists_preamble(project_config["name"]))
        for d, hash, prefix in dependencies:
            f.write(f"\ndevelop({d})")
        f.write("\n")


def cmake_presets(project_config, dependencies, view_path):
    source_path = Path(project_config["source"])
    cxxstd = project_config["cxxstd"]["value"]
    configurePresets, cacheVariables = "configurePresets", "cacheVariables"
    view_lib_dirs = [(view_path / d).resolve().as_posix() for d in ("lib", "lib64")]
    allCacheVariables = {
        "CMAKE_BUILD_TYPE": {"type": "STRING", "value": "RelWithDebInfo"},
        "CMAKE_CXX_EXTENSIONS": {"type": "BOOL", "value": "OFF"},
        "CMAKE_CXX_STANDARD_REQUIRED": {"type": "BOOL", "value": "ON"},
        "CMAKE_CXX_STANDARD": {"type": "STRING", "value": cxxstd},
        "CMAKE_INSTALL_RPATH_USE_LINK_PATH": {"type": "BOOL", "value": "ON"},
        "CMAKE_INSTALL_RPATH": {"type": "STRING",
                                "value": ";".join(view_lib_dirs)},
    }

    # Pull project-specific presets from each dependency.
    for dep_name, dep_hash, dep_prefix in dependencies:
        allCacheVariables[f"{dep_name}_HASH"] = dep_hash
        allCacheVariables[f"{dep_name}_INSTALL_PREFIX"] = dep_prefix

        pkg_presets_file = source_path / dep_name / "CMakePresets.json"
        if not pkg_presets_file.exists():
            continue

        with open(pkg_presets_file, "r") as f:
            pkg_presets = json.load(f)
            pkg_config_presets = pkg_presets[configurePresets]
            default_presets = next(
                filter(lambda s: s["name"] == "from_product_deps", pkg_config_presets)
            )
            for key, value in default_presets[cacheVariables].items():
                if key.startswith(dep_name):
                    allCacheVariables[key] = value

    presets = {
        configurePresets: [
            {
                cacheVariables: allCacheVariables,
                "description": "Configuration settings as created by 'spack mpd new-project'",
                "displayName": "Configuration from mpd new-project",
                "name": "default",
            }
        ],
        "version": 3,
    }

    with open((source_path / "CMakePresets.json").absolute(), "w") as f:
        json.dump(presets, f, indent=4)


def make_cmake_files(project_config, cmake_args, dependencies, view_path):
    cmake_develop(project_config, cmake_args)
    cmake_lists(project_config, dependencies)
    cmake_presets(project_config, dependencies, view_path)


def remove_view(local_env_dir):
    spack_env = Path(local_env_dir) / ".spack-env"
    view_path = (spack_env / "view")
    if view_path.is_symlink():
        view_path.unlink()
    else:
        shutil.rmtree(view_path, ignore_errors=True)
    shutil.rmtree(spack_env / "._view", ignore_errors=True)


def ordered_roots(env, package_requirements):
    packages = list(package_requirements.keys())

    # Build comparison table with parent < child represented as the pair (parent, child)
    parent_child = []
    install_prefixes = {}
    for s in env.all_specs():
        if s.name not in package_requirements:
            continue
        parent_child.extend((s.name, d.name) for d in s.traverse(order="topo", root=False)
                            if d.name in packages)
        install_prefixes[s.name] = (s.name, s.dag_hash(), s.prefix)

    def compare_parents(a, b):
        if (a, b) in parent_child:
            return -1
        if (b, a) in parent_child:
            return 1
        return 0

    sorted_packages = sorted(packages, key=functools.cmp_to_key(compare_parents), reverse=True)
    return [install_prefixes[p] for p in sorted_packages]


def verify_no_missing_intermediate_deps(env, packages) -> None:
    missing_intermediate_deps = {}
    for n in env.all_specs():
        # Skip the packages under development
        if n.name in packages:
            continue

        checked_out_deps = [p.name for p in n.dependencies() if p.name in packages]
        if checked_out_deps:
            missing_intermediate_deps[n.name] = checked_out_deps

    if missing_intermediate_deps:
        indent = " " * len("==> Error: ")
        error_msg = (
            "The following packages are intermediate dependencies of the\n"
            f"{indent}currently cloned packages and must also be cloned:\n"
        )
        for pkg_name, checked_out_deps in sorted(missing_intermediate_deps.items()):
            checked_out_deps_str = ", ".join(checked_out_deps)
            error_msg += "\n - " + bold(pkg_name)
            error_msg += f" (depends on {checked_out_deps_str})"
        print()
        tty.die(error_msg + "\n")


def absent_dependencies(env, packages) -> list:
    absent = []
    for n in env.all_specs():
        # Skip the packages under development
        if n.name in packages:
            continue

        if n.install_status() == InstallStatus.absent:
            absent.append(n.cshort_spec)

    return sorted(set(absent))


# Stolen shamelessly from https://stackoverflow.com/a/60321833/3585575
def deep_update(original, update):
    """Recursively update a dict.

    Subdict's won't be overwritten but also updated.
    """
    if not isinstance(original, abc.Mapping):
        return update
    for key, value in update.items():
        if isinstance(value, abc.Mapping):
            original[key] = deep_update(original.get(key, {}), value)
        else:
            original[key] = value
    return original


def concretize_project(project_config, yes_to_all):
    proto_envs = [find_environment(e) for e in project_config["envs"]]
    package_requirements = {}
    for penv in proto_envs:
        penv_config = {}
        with open(penv.manifest_path, "r") as f:
            penv_config = syaml.load(f)
        deep_update(package_requirements, penv_config.mlget(["spack", "packages"], {}))

    packages = project_config["packages"]
    new_package_requirements = copy.deepcopy(packages)
    new_package_requirements.update(project_config["dependencies"])
    deep_update(package_requirements, new_package_requirements)

    print()
    tty.msg(cyan("Determining dependencies") + " (this may take a few minutes)")

    reuse_block = {"from": [{"type": "local"}, {"type": "external"}]}
    full_block = dict(
        include_concrete=[penv.path for penv in proto_envs],
        specs=list(packages.keys()),
        concretizer=dict(unify=True, reuse=reuse_block),
        packages=package_requirements,
    )

    # Include compiler as a definition in the environment specification.
    compiler = project_config["compiler"]
    if compiler:
        compiler = compilers.find(compiler["value"])[0]
        compiler_str = [YamlQuote(compiler)]
        full_block.update(definitions=[dict(compiler=compiler_str)])

    local_env_dir = project_config["local"]
    name = project_config["name"]

    # Always start fresh
    env_file = make_yaml_file(name, dict(spack=full_block), prefix=local_env_dir)

    tty.info(gray("Creating initial environment"))
    if ev.exists(name):
        ev.read(name).destroy()
    env = ev.create(name, init_file=env_file)
    update(project_config, status="created")

    tty.info(gray("Concretizing initial environment"))
    with env, env.write_transaction():
        env.concretize()
        env.write(regenerate=False)

    verify_no_missing_intermediate_deps(env, packages)

    # Handle package-specific CMake args as provided by the Spack package
    cmake_args = {}
    for s in env.concrete_roots():
        if s.name not in packages:
            continue
        cmake_args[s.name] = s.package.cmake_args()

    # Create properly ordered CMake file
    make_cmake_files(project_config,
                     cmake_args,
                     ordered_roots(env, packages),
                     Path(env.view_path_default))

    # Make development environment from initial environment
    #   - Then remove the embedded '.spack-env/view' subdirectory, which will induce a
    #     SpackEnvironmentViewError exception if not removed.
    tty.info(cyan("Creating local development environment"))
    shutil.copytree(env.path, local_env_dir, symlinks=True, dirs_exist_ok=True)
    remove_view(local_env_dir)

    # Now add the first-order dependencies
    env = ev.Environment(local_env_dir)
    developed_specs = [s for _, s in env.concretized_specs() if s.name in packages]
    first_order_deps = {}
    for s in developed_specs:
        for depth, dep in traverse.traverse_nodes([s], depth=True):
            if depth != 1:
                continue
            if dep.name in packages:
                continue
            first_order_deps[dep.name] = dep.format(
                "{name}{@version}"
                "{%compiler.name}{@compiler.version}{compiler_flags}"
                "{variants}"
            )

    tty.msg(gray("Adjusting specifications for package development"))
    subprocess.run(["spack", "-e", local_env_dir, "add"] + list(first_order_deps.keys()))

    tty.info(gray("Finalizing concretization"))
    remove_view(local_env_dir)
    with env, env.write_transaction():
        env.concretize()
        env.write()

    subprocess.run(["spack", "-e", local_env_dir, "rm"] + list(packages.keys()))
    with env, env.write_transaction():
        env.concretize()
        env.write()

    update(project_config, status="concretized")

    if absent := absent_dependencies(env, packages):
        def _parens_number(i):
            return f"({i})"

        msg = "The following packages will be installed:\n"
        width = len(_parens_number(len(absent)))
        for i, dep in enumerate(absent):
            num_str = _parens_number(i + 1)
            msg += f"\n {num_str:>{width}}  {dep}"
        msg += "\n\nPlease ensure you have adequate space for these installations.\n"
        print()
        tty.msg(msg)
    else:
        yes_to_all = True

    if not yes_to_all:
        should_install = tty.get_yes_or_no("Would you like to continue?", default=True)
    else:
        should_install = True

    if should_install is False:
        print()
        gray_gt = gray(">")
        tty.msg(
            f"To install the development environment later, invoke:\n\n"
            f"  {gray_gt} spack env activate {local_env_dir}\n"
            f"  {gray_gt} spack install -j<ncores>\n"
            f"  {gray_gt} spack env deactivate\n"
        )
        return

    ncores = os.cpu_count() // 2
    if not yes_to_all:
        ncores = get_number("Specify number of cores to use", default=ncores)

    tty.msg(gray("Installing development environment\n"))
    # As of Spack 0.23, an environment should be explicitly activated before invoking
    # install (i.e. don't use 'spack -e <env> install').
    result = subprocess.run(f"spack env activate {local_env_dir}; spack install -j{ncores}",
                            shell=True)

    if result.returncode == 0:
        print()
        update(project_config, status="ready")
        tty.msg(f"{bold(name)} is ready for development "
                f"(e.g type {cyan('spack mpd build ...')})\n")
