import copy
import json
import os
import re
import shutil
import subprocess
import time
from collections import abc
from pathlib import Path
try:
    from _vendoring.ruamel.yaml.scalarstring import SingleQuotedScalarString as YamlQuote
except:
    from ruamel.yaml.scalarstring import SingleQuotedScalarString as YamlQuote
import llnl.util.tty as tty

import spack.builder as builder
import spack.cmd
import spack.compilers
import spack.config
import spack.environment as ev
import spack.util.spack_yaml as syaml
from spack import traverse
from spack.spec import InstallStatus

from .config import update
from .util import bold, cyan, get_number, gray, make_yaml_file

SUBCOMMAND = "new-project"
ALIASES = ["n"]

CMAKE_CACHE_VARIABLE_PATTERN = re.compile(r"-D(.*):(.*)=(.*)")


def preset_from_product_deps(preset):
    return preset["name"] == "from_product_deps"


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
  if (COMMAND set_${{pkg_with_underscores}}_variables)
    cmake_language(CALL "set_${{pkg_with_underscores}}_variables")
  endif()
  add_subdirectory(${{pkg}})
  if (COMMAND unset_${{pkg_with_underscores}}_variables)
    cmake_language(CALL "unset_${{pkg_with_underscores}}_variables")
  endif()
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
    # Select compiler
    compilers = []
    all_compilers = spack.compilers.config.all_compilers()
    if desired_compiler := project_config.get("compiler"):
        desired_compiler = desired_compiler["value"]
        compilers = [c for c in all_compilers if c.satisfies(desired_compiler)]

        if not compilers:
            desired_compiler_variant = project_config["compiler"]["variant"]
            tty.die(f"No compiler found that corresponds to '{desired_compiler_variant}'")

        # Most recent version wins
        compilers.sort(key=lambda spec: spec.version, reverse=True)

    # If no compilers specified, find preferred one
    if not compilers:
        candidates = {c.name: c for c in all_compilers}
        preferred_compilers = spack.config.get("packages:all:compiler", list())
        for c in preferred_compilers:
            if candidate := candidates.get(c):
                compilers.append(candidate)
                break

    if not compilers:
        tty.die("No default compiler available--you must specify the compiler (e.g. %gcc@x.y)")

    cxxstd = project_config["cxxstd"]["value"]
    view_lib_dirs = [(view_path / d).resolve().as_posix() for d in ("lib", "lib64")]

    compiler_paths = compilers[0].extra_attributes["compilers"]
    allCacheVariables = {
        "CMAKE_BUILD_TYPE": {"type": "STRING", "value": "RelWithDebInfo"},
        "CMAKE_C_COMPILER": {"type": "PATH", "value": compiler_paths["c"]},
        "CMAKE_CXX_COMPILER": {"type": "PATH", "value": compiler_paths["cxx"]},
        "CMAKE_CXX_EXTENSIONS": {"type": "BOOL", "value": "OFF"},
        "CMAKE_CXX_STANDARD_REQUIRED": {"type": "BOOL", "value": "ON"},
        "CMAKE_CXX_STANDARD": {"type": "STRING", "value": cxxstd},
        "CMAKE_INSTALL_RPATH_USE_LINK_PATH": {"type": "BOOL", "value": "ON"},
        "CMAKE_INSTALL_RPATH": {"type": "STRING",
                                "value": ";".join(view_lib_dirs)},
    }

    source_path = Path(project_config["source"])
    configurePresets, cacheVariables = "configurePresets", "cacheVariables"

    # Pull project-specific presets from each dependency.
    for dep_name, dep_hash, dep_prefix in dependencies:
        allCacheVariables[f"{dep_name}_HASH"] = dep_hash
        allCacheVariables[f"{dep_name}_INSTALL_PREFIX"] = dep_prefix

        pkg_presets_file = source_path / dep_name / "CMakePresets.json"
        if not pkg_presets_file.exists():
            continue

        with open(pkg_presets_file, "r") as f:
            pkg_presets = json.load(f)
            default_presets = pkg_presets[configurePresets]
            if any(preset_from_product_deps(s) for s in default_presets):
                default_presets = next(filter(preset_from_product_deps, default_presets))

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


def no_dependents(packages):
    no_incoming_edges = []
    for pkg in packages.keys():
        found = False
        for deps in packages.values():
            if pkg in deps:
                found = True
                break

        if not found:
            no_incoming_edges.append(pkg)
    return no_incoming_edges


def toposort_packages(packages):
    # Stolen from https://en.wikipedia.org/wiki/Topological_sorting#Kahn's_algorithm
    #
    #   Kahn, Arthur B. (1962), "Topological sorting of large networks",
    #     Communications of the ACM, 5 (11): 558–562

    packages = copy.deepcopy(packages)

    L = []  # Empty list that will contain the sorted elements
    S = no_dependents(packages)  # Nodes with no incoming edges/dependents

    num_candidates = len(S)
    while num_candidates:
        n = S.pop()
        L.append(n)
        children = packages.pop(n)
        updated_no_incoming_edges = no_dependents(packages)
        for child in children:
            if child in updated_no_incoming_edges:
                S.append(child)
        num_candidates = len(S)

    assert not packages  # Spack will not allow a cycle
    return reversed(L)  # We want the lowest-level packages first


def ordered_roots(env, package_requirements):
    packages = list(package_requirements.keys())

    # Build comparison table with parent < child represented as the pair (parent, child)
    parent_children = {}
    install_prefixes = {}
    for s in env.all_specs():
        if s.name not in package_requirements:
            continue
        parent_children[s.name] = [d.name for d in s.traverse(order="topo", root=False)
                                   if d.name in packages]
        install_prefixes[s.name] = (s.name, s.dag_hash(), s.prefix)

    sorted_packages = toposort_packages(parent_children)
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


def concretize_project(project_config, yes_to_all):
    packages = project_config["packages"]

    # Omit ignorable packages
    for ignore in project_config["ignored"]:
        if ignore in packages:
            del packages[ignore]

    package_requirements = copy.deepcopy(packages)
    package_requirements.update(project_config["dependencies"])

    print()
    tty.msg(cyan("Determining dependencies") + " (this may take a few minutes)")

    from_items = [{"type": "local"}, {"type": "external"}]
    if proto_env := project_config["env"]:
        from_items += [{"type": "environment", "path": proto_env}]
    reuse_block = {"from": from_items}
    view_dict = {"default": dict(root=".spack-env/view", exclude=['gcc-runtime'])}
    full_block = dict(
        specs=list(packages.keys()),
        concretizer=dict(unify=True, reuse=reuse_block),
        view=view_dict,
        packages=package_requirements,
    )

    # Include compiler as a definition in the environment specification.
    first_order_deps = {"cmake"}
    if compiler := project_config.get("compiler"):
        found_compilers = spack.cmd.parse_specs(compiler["value"])
        if not found_compilers:
            indent = " " * len("==> Error: ")
            print()
            tty.die(f"The compiler {bold(compiler['value'])} is not available.\n"
                    f"{indent}See {cyan('spack compiler list')} for available compilers.\n"
                    f"{indent}Also see {cyan('spack compiler add --help')}.\n")
        compiler_str = [YamlQuote(found_compilers[0])]
        first_order_deps.add(compiler_str[0])

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

        # Instead of receiving the CMake args directly from the package, we use the
        # builder interface, which also supports packages that provide a CMakeBuilder
        # class.
        pkg_builder = builder.create(s.package)
        if cmake_args_method := getattr(pkg_builder, "cmake_args", False):
            cmake_args[s.name] = cmake_args_method()

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
    for s in developed_specs:
        for depth, dep in traverse.traverse_nodes([s], depth=True):
            if depth != 1:
                continue
            if dep.name in packages:
                continue
            first_order_deps.add(dep.name)

    new_roots = "Adding the following packages as top-level dependencies:"
    for dep in sorted(first_order_deps):
        new_roots += f"\n    - {dep}"
    tty.msg(gray(new_roots))
    subprocess.run(
        ["spack", "-e", local_env_dir, "add"] + list(first_order_deps),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with env, env.write_transaction():
        env.concretize()
        env.write()

    tty.info(gray("Finalizing concretization"))
    remove_view(local_env_dir)

    # Lastly, remove the developed packages from the environment
    subprocess.run(["spack", "-e", local_env_dir, "rm"] + list(packages.keys()),
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
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
