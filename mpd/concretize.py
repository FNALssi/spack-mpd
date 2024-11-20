import copy
import functools
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from ruamel.yaml.scalarstring import SingleQuotedScalarString as YamlQuote

import llnl.util.tty as tty

import spack.compilers as compilers
import spack.environment as ev
from spack import traverse
from spack.parser import SPLIT_KVP
from spack.spec import InstallStatus

from .config import update
from .util import bold, cyan, get_number, gray, make_yaml_file

SUBCOMMAND = "new-project"
ALIASES = ["n"]

CMAKE_CACHE_VARIABLE_PATTERN = re.compile(r"-D(.*):(.*)=(.*)")


def setup_subparser(subparsers):
    new_project = subparsers.add_parser(
        SUBCOMMAND,
        description="create MPD development area",
        aliases=ALIASES,
        help="create MPD development area",
    )
    new_project.add_argument("--name", required=True, help="(required)")
    new_project.add_argument(
        "-T",
        "--top",
        default=Path.cwd(),
        help="top-level directory for MPD area\n(default: %(default)s)",
    )
    new_project.add_argument(
        "-S",
        "--srcs",
        help="directory containing repositories to develop\n"
        "(default: <top-level directory>/srcs)",
    )
    new_project.add_argument(
        "-f", "--force", action="store_true", help="overwrite existing project with same name"
    )
    new_project.add_argument(
        "-E",
        "--env",
        default=[],
        help="environments from which to create project\n(multiple allowed)",
        action="append",
    )
    new_project.add_argument(
        "-y", "--yes-to-all", action="store_true", help="Answer yes/default to all prompts"
    )
    new_project.add_argument("variants", nargs="*", help="variants to apply to developed packages")


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
  set({variable} "{value}" CACHE {vartype} "")
"""
            unset_contents += f"""  # Restore/unset {variable}
  if(DEFINED OLD_{variable})
    set({variable} "${{OLD_{variable}}}")
    unset(OLD_{variable})
  else()
    unset({variable})
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
    cxxstd_variant = project_config["cxxstd"]
    cxx_standard = SPLIT_KVP.match(cxxstd_variant).group(3)
    configurePresets, cacheVariables = "configurePresets", "cacheVariables"
    view_lib_dirs = [(view_path / d).resolve().as_posix() for d in ("lib", "lib64")]
    allCacheVariables = {
        "CMAKE_BUILD_TYPE": {"type": "STRING", "value": "RelWithDebInfo"},
        "CMAKE_CXX_EXTENSIONS": {"type": "BOOL", "value": "OFF"},
        "CMAKE_CXX_STANDARD_REQUIRED": {"type": "BOOL", "value": "ON"},
        "CMAKE_CXX_STANDARD": {"type": "STRING", "value": cxx_standard},
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


def concretize_project(project_config, yes_to_all):
    packages = project_config["packages"]
    package_requirements = copy.deepcopy(packages)
    package_requirements.update(project_config["dependencies"])

    proto_envs = [find_environment(e) for e in project_config["envs"]]

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
        compiler = compilers.find(compiler)[0]
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

    # Handle package-specific CMake args as provided by the Spack package
    cmake_args = {}
    for s in env.concrete_roots():
        if s.name not in packages:
            continue
        cmake_args[s.name] = s.package.cmake_args()

    # Create properly ordered CMake file
    make_cmake_files(project_config,
                     cmake_args,
                     ordered_roots(env, package_requirements),
                     Path(env.view_path_default))

    # Make development environment from initial environment
    #   - Then remove the embedded '.spack-env/view' subdirectory, which will induce a
    #     SpackEnvironmentViewError exception if not removed.
    tty.info(cyan("Creating local development environment"))
    shutil.copytree(env.path, local_env_dir, symlinks=True, dirs_exist_ok=True)
    remove_view(local_env_dir)

    # Now add the first-order dependencies
    env = ev.Environment(local_env_dir)
    developed_specs = [s for _, s in env.concretized_specs() if s.name in package_requirements]
    first_order_deps = {}
    for s in developed_specs:
        for depth, dep in traverse.traverse_nodes([s], depth=True):
            if depth != 1:
                continue
            if dep.name in package_requirements:
                continue
            first_order_deps[dep.name] = dep.format(
                "{name}{@version}"
                "{%compiler.name}{@compiler.version}{compiler_flags}"
                "{variants}"
            )

    tty.msg(gray("Adjusting specifications for package development"))
    subprocess.run(["spack", "-e", ".", "add"] + list(first_order_deps.keys()),
                   stdout=subprocess.DEVNULL,
                   cwd=local_env_dir)

    tty.info(gray("Finalizing concretization"))
    remove_view(local_env_dir)
    with env, env.write_transaction():
        env.concretize()
        env.write()

    subprocess.run(["spack", "-e", ".", "rm"] + list(package_requirements.keys()),
                   stdout=subprocess.DEVNULL,
                   cwd=local_env_dir)
    with env, env.write_transaction():
        env.concretize()
        env.write()

    absent_dependencies = []
    missing_intermediate_deps = {}
    for n in env.all_specs():
        # Skip the packages under development
        if n.name in package_requirements:
            continue

        if n.install_status() == InstallStatus.absent:
            absent_dependencies.append(n.cshort_spec)

        checked_out_deps = [p.name for p in n.dependencies() if p.name in package_requirements]
        if checked_out_deps:
            missing_intermediate_deps[n.name] = checked_out_deps

    if missing_intermediate_deps:
        error_msg = (
            "The following packages are intermediate dependencies of the\n"
            "currently cloned packages and must also be cloned:\n"
        )
        for pkg_name, checked_out_deps in sorted(missing_intermediate_deps.items()):
            checked_out_deps_str = ", ".join(checked_out_deps)
            error_msg += "\n - " + bold(pkg_name)
            error_msg += f" (depends on {checked_out_deps_str})"
        print()
        tty.die(error_msg + "\n")

    update(project_config, status="concretized")

    if absent_dependencies:
        # Remove duplicates, preserving order
        unique_absent_dependencies = []
        for dep in absent_dependencies:
            if dep not in unique_absent_dependencies:
                unique_absent_dependencies.append(dep)
        absent_dependencies = unique_absent_dependencies

        def _parens_number(i):
            return f"({i})"

        msg = "\nThe following packages will be installed:\n"
        width = len(_parens_number(len(absent_dependencies)))
        for i, dep in enumerate(sorted(absent_dependencies)):
            num_str = _parens_number(i + 1)
            msg += f"\n {num_str:>{width}}  {dep}"
        msg += "\n\nPlease ensure you have adequate space for these installations.\n"
        tty.msg(msg)
    else:
        yes_to_all = True

    if not yes_to_all:
        should_install = tty.get_yes_or_no("Would you like to continue?", default=True)
    else:
        should_install = True

    if should_install is False:
        print()
        tty.msg(
            f"To install the development environment later, invoke:\n\n"
            f"  spack -e {local_env_dir} install -j<ncores>\n"
        )
        return

    if not yes_to_all:
        ncores = get_number("Specify number of cores to use", default=os.cpu_count() // 2)
    else:
        ncores = os.cpu_count() // 2

    tty.msg(gray("Installing development environment\n"))
    result = subprocess.run(["spack", "-e", ".", "install", f"-j{ncores}"], cwd=local_env_dir)

    if result.returncode == 0:
        print()
        update(project_config, status="installed")
        tty.msg(f"{bold(name)} is ready for development "
                f"(e.g type {cyan('spack mpd build ...')})\n")
