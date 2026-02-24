import copy
import json
import os
import re
import subprocess
import time
from pathlib import Path

from spack.vendor.ruamel.yaml.scalarstring import SingleQuotedScalarString as YamlQuote

import spack.builder as builder
import spack.cmd
import spack.compilers
import spack.compilers.config
import spack.concretize
import spack.environment as ev
import spack.llnl.util.tty as tty
import spack.store
import spack.util.spack_yaml as syaml
from spack import traverse
from spack.spec import InstallStatus, Spec

from .config import update
from .util import bold, cyan, get_number, gray, make_yaml_file, yellow

SUBCOMMAND = "new-project"
ALIASES = ["n"]

CMAKE_CACHE_VARIABLE_PATTERN = re.compile(r"-D(.*):(.*)=(.*)")


def all_available_compilers():
    # Pilfered from https://github.com/spack/spack/blob/182c615df98bda5d3c1e26513e3a52c40b4efbec/lib/spack/spack/cmd/compiler.py#L222
    supported_compilers = spack.compilers.config.supported_compilers()

    def _is_compiler(x):
        return x.name in supported_compilers and x.package.supported_languages and not x.external

    compilers_from_store = [x for x in spack.store.STORE.db.query() if _is_compiler(x)]
    compilers_from_yaml = spack.compilers.config.all_compilers(scope=None, init_config=False)
    return compilers_from_yaml + compilers_from_store


def preset_is(name: str):
    def preset_predicate(preset: dict):
        return preset["name"] == name

    return preset_predicate


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
    return (
        begin_set_macro(name)
        + set_contents
        + end()
        + "\n"
        + begin_unset_macro(name)
        + unset_contents
        + end()
        + "\n"
    )


def cmake_develop(project_config, package_cmake_args):
    project_name = project_config["name"]
    source_path = Path(project_config["source"])
    file_dir = Path(__file__).resolve().parent
    with open((source_path / "develop.cmake").absolute(), "w") as out:
        for name, args in package_cmake_args.items():
            out.write(f"# {name} variables\n" + cmake_package_variables(name, args))
        out.write(
            f"""set(CWD "{file_dir}")
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
"""
        )


def cmake_lists_preamble(project_name, develop_cetmodules, cetmodules4):
    date = time.strftime("%Y-%m-%d")
    preamble = """cmake_minimum_required(VERSION 3.24...4.1 FATAL_ERROR)
enable_testing()
include(develop.cmake)

"""
    if develop_cetmodules:
        preamble += "develop(cetmodules)\n\n"

    if cetmodules4:
        preamble += """include(FetchContent)
FetchContent_Declare(
  cetmodules
  GIT_REPOSITORY https://github.com/FNALssi/cetmodules
  GIT_TAG 39f03b11 # v4.01.01
  FIND_PACKAGE_ARGS 4.01.01
  )

FetchContent_MakeAvailable(cetmodules)
find_package(cetmodules 4.01.01 REQUIRED)
"""

    preamble += f"project({project_name}-{date} LANGUAGES NONE)\n\n"
    return preamble


def cmake_lists(project_config, dependencies, cetmodules4):
    source_path = Path(project_config["source"])
    develop_cetmodules = any("cetmodules" in p for p in [d[0] for d in dependencies])
    with open((source_path / "CMakeLists.txt").absolute(), "w") as f:
        f.write(
            cmake_lists_preamble(
                project_config["name"],
                develop_cetmodules=develop_cetmodules,
                cetmodules4=cetmodules4,
            )
        )
        for d, hash, prefix in dependencies:
            if d == "cetmodules":
                continue
            f.write(f"\ndevelop({d})")
        f.write("\n")


def cmake_presets(project_config, dependencies, cetmodules4, view_path):
    # Use the compiler that was already selected and validated in project_config_from_args
    compiler_paths = project_config["compiler_paths"]

    cxxstd = project_config["cxxstd"]["value"]
    view_lib_dirs = [(view_path / d).resolve().as_posix() for d in ("lib", "lib64")]

    configure_presets = {
        "CMAKE_BUILD_TYPE": {"type": "STRING", "value": "RelWithDebInfo"},
        "CMAKE_CXX_EXTENSIONS": {"type": "BOOL", "value": "OFF"},
        "CMAKE_CXX_STANDARD_REQUIRED": {"type": "BOOL", "value": "ON"},
        "CMAKE_CXX_STANDARD": {"type": "STRING", "value": cxxstd},
        "CMAKE_INSTALL_RPATH_USE_LINK_PATH": {"type": "BOOL", "value": "ON"},
        "CMAKE_INSTALL_RPATH": {"type": "STRING", "value": ";".join(view_lib_dirs)},
    }

    if cetmodules4:
        configure_presets["CMAKE_PROJECT_TOP_LEVEL_INCLUDES"] = "CetProvideDependency"

    # Set C/CXX compilers depending on which languages are needed
    languages = project_config["languages"]
    if "c" in languages:
        configure_presets["CMAKE_C_COMPILER"] = {"type": "PATH", "value": compiler_paths["c"]}
    if "cxx" in languages:
        configure_presets["CMAKE_CXX_COMPILER"] = {"type": "PATH", "value": compiler_paths["cxx"]}
    if "python" in languages:
        # It is sufficient to use the *local* view path for CMake to locate Python
        local_view_path = Path(project_config["local"]) / ".spack-env" / "view"
        configure_presets["Python_ROOT"] = {
            "type": "PATH",
            "value": local_view_path.resolve().as_posix(),
        }

    allCacheVariables = {"configurePresets": configure_presets}

    source_path = Path(project_config["source"])
    preset_types = [
        f"{item}Presets" for item in ("configure", "build", "test", "package", "workflow")
    ]
    cache_key = "cacheVariables"
    max_presets_version = 3

    # Pull project-specific presets from each dependency.
    for dep_name, dep_hash, dep_prefix in dependencies:
        allCacheVariables[f"{dep_name}_HASH"] = dep_hash
        allCacheVariables[f"{dep_name}_INSTALL_PREFIX"] = dep_prefix

        pkg_presets_file = source_path / dep_name / "CMakePresets.json"
        if not pkg_presets_file.exists():
            continue

        with open(pkg_presets_file, "r") as f:
            pkg_presets = json.load(f)
            input_presets_version = pkg_presets["version"]
            if input_presets_version > max_presets_version:
                max_presets_version = input_presets_version
            for preset_type in [s for s in preset_types if s in pkg_presets]:
                presets = pkg_presets[preset_type]
                preset = next(
                    filter(preset_is("from_product_deps"), presets),
                    next(filter(preset_is("default"), presets), None),
                )
                if not (preset and cache_key in preset):
                    continue
                for key, value in preset[cache_key].items():
                    if key.startswith(dep_name):
                        allCacheVariables[preset_type][key] = value

    presets = {"version": max_presets_version}
    for preset_type in [s for s in preset_types if s in allCacheVariables]:
        presets.update(
            {
                preset_type: [
                    {
                        cache_key: allCacheVariables[preset_type],
                        "description": "settings as created by 'spack mpd new-project'",
                        "displayName": "settings from mpd new-project",
                        "name": "default",
                    }
                ]
            }
        )

    with open((source_path / "CMakePresets.json").absolute(), "w") as f:
        json.dump(presets, f, indent=4)


def make_cmake_files(project_config, cmake_args, dependencies, cetmodules4, view_path):
    cmake_develop(project_config, cmake_args)
    cmake_lists(project_config, dependencies, cetmodules4)
    cmake_presets(project_config, dependencies, cetmodules4, view_path)


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
        parent_children[s.name] = [
            d.name for d in s.traverse(order="topo", root=False) if d.name in packages
        ]
        install_prefixes[s.name] = (s.name, s.dag_hash(), s.prefix)

    sorted_packages = toposort_packages(parent_children)
    return [install_prefixes[p] for p in sorted_packages]


def verify_no_missing_intermediate_deps(env, packages) -> None:
    direct_dependents = {}
    missing_intermediate_deps = {}

    for n in env.all_specs():
        all_dep_names = [p.name for p in n.dependencies()]
        if not all_dep_names:
            continue

        # Map to look up dependents from dependencies
        for d in all_dep_names:
            direct_dependents.setdefault(d, list()).append(n.name)

        # Skip the packages under development
        if n.name in packages:
            continue

        # Package that is not under development but should be
        checked_out_deps = [name for name in all_dep_names if name in packages]
        if checked_out_deps:
            missing_intermediate_deps[n.name] = checked_out_deps

    if missing_intermediate_deps:
        indent = " " * len("==> Error: ")
        error_msg = (
            "The following packages are intermediate dependencies of the\n"
            f"{indent}currently cloned packages and must also be cloned:\n"
        )
        for pkg_name, checked_out_deps in sorted(missing_intermediate_deps.items()):
            direct_dependents_str = ", ".join(direct_dependents.get(pkg_name, []))
            checked_out_deps_str = ", ".join(checked_out_deps)
            error_msg += "\n - " + bold(pkg_name)
            error_msg += f"\n     required by: {yellow(direct_dependents_str)}"
            error_msg += f"\n     depends on:  {yellow(checked_out_deps_str)}"
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

    # Make sure that all developed-package configurations override any inherited configurations
    packages_with_overrides = {f"{key}:": value for key, value in packages.items()}

    package_requirements = copy.deepcopy(packages_with_overrides)
    package_requirements.update(project_config["dependencies"])

    # Build the "all" configuration
    all_config = {
        "providers": {"libc": ["glibc"], "zlib-api:": ["zlib"]},
        "variants": ["generator=ninja"],
        "target": ["x86_64_v3"],
    }

    package_requirements["all"] = all_config

    print()
    tty.msg(cyan("Determining dependencies") + " (this may take a few minutes)")

    from_items = []
    include_list = []
    if proto_env := project_config["env"]:
        # If an external environment is used, we really, really want to use that one.
        from_items += [{"type": "environment", "path": proto_env}]

        # Read the proto_env's spack.yaml to extract the include list
        proto_env_yaml = None
        if ev.exists(proto_env):
            proto_env_yaml = Path(ev.read(proto_env).manifest_path)
        else:
            proto_env_yaml = Path(proto_env) / "spack.yaml"

        if proto_env_yaml.exists():
            with open(proto_env_yaml, "r") as f:
                proto_config = syaml.load(f)
                if proto_config and "spack" in proto_config:
                    include_list = proto_config["spack"].get("include", [])
    else:
        from_items += [{"type": "local"}, {"type": "external"}]

    reuse_block = {"from": from_items}

    # Specify the subdirectory path(s) of the chosen compiler
    compiler_dir_paths = set(str(Path(p).parent) for p in project_config["compiler_paths"].values())
    prepend_dirs = dict(PATH=":".join(compiler_dir_paths))

    default_view_dict = dict(root=".spack-env/view", exclude=["gcc-runtime"])

    full_block = dict(
        env_vars=dict(prepend_path=prepend_dirs),
        config=dict(deprecated=True),
        specs=list(packages.keys()),
        concretizer=dict(unify=True, reuse=reuse_block),
        view=dict(default=default_view_dict),
        packages=package_requirements,
    )

    # Add the include list if it exists
    if include_list:
        full_block["include"] = include_list

    local_env_dir = project_config["local"]
    name = project_config["name"]

    # Always start fresh
    env_file = make_yaml_file("spack", dict(spack=full_block), prefix=local_env_dir)

    tty.info(gray("Creating initial environment"))
    if ev.exists(name):
        ev.read(name).destroy()
    env = ev.create(name, init_file=env_file)
    update(project_config, status="created")

    tty.info(gray("Concretizing initial environment"))
    subprocess.run(["spack", "-e", name, "concretize"], capture_output=True).check_returncode()

    env = ev.read(name)
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

    # Make development environment starting with initial environment configuration
    tty.info(cyan("Creating local development environment"))

    # Now add the first-order dependencies
    # Include compiler as a definition in the environment specification.
    first_order_deps = {"cmake"}

    chosen_compiler = None
    if compiler := project_config.get("compiler"):
        found_compilers = spack.cmd.parse_specs(compiler["value"])
        if not found_compilers:
            indent = " " * len("==> Error: ")
            print()
            tty.die(
                f"The compiler {bold(compiler['value'])} is not available.\n"
                f"{indent}See {cyan('spack compiler list')} for available compilers.\n"
                f"{indent}Also see {cyan('spack compiler add --help')}.\n"
            )
        chosen_compiler = found_compilers[0]

    # Cetmodules 4 is used by default
    cetmodules4 = True
    developed_specs = [s for _, s in env.concretized_specs() if s.name in packages]
    for s in developed_specs:
        for depth, dep in traverse.traverse_edges([s], cover="edges", depth=True):
            if depth != 1:
                # Only the first-order dependencies are added to the development environment
                continue
            if dep.spec.name in packages:
                # Some packages under development may depend on other packages under development.
                # We remove such dependencies here.
                continue
            if dep.spec.satisfies(chosen_compiler):
                # The development environment should not include the compiler as a root spec.
                continue
            if dep.spec.name == "cetmodules":
                # Do not use cetmodules4 if one of the dependencies does not use version 4.
                cetmodules4 = cetmodules4 and dep.spec.version.up_to(1) == 4
                continue
            if dep.spec.external:
                # We don't need to (and probably shouldn't) include things like glibc.
                continue
            first_order_deps.add(dep.spec.name)

    # gcc-runtime is a build-time dependency that will be built if needed.
    first_order_deps.discard("gcc-runtime")

    # Create properly ordered CMake file
    make_cmake_files(
        project_config,
        cmake_args,
        ordered_roots(env, packages),
        cetmodules4,
        Path(env.view_path_default),
    )

    new_roots = "Adding the following packages as top-level dependencies:"
    sorted_first_order_deps = sorted(first_order_deps)
    for dep in sorted_first_order_deps:
        new_roots += f"\n    - {dep}"
    tty.msg(gray(new_roots))
    subprocess.run(
        ["spack", "-D", local_env_dir, "add"] + list(sorted_first_order_deps), capture_output=True
    ).check_returncode()

    subprocess.run(
        ["spack", "-D", local_env_dir, "concretize"], capture_output=True
    ).check_returncode()

    tty.info(gray("Finalizing concretization"))

    # Lastly, remove the developed packages from the environment
    subprocess.run(
        ["spack", "-D", local_env_dir, "rm"] + list(packages.keys()), capture_output=True
    ).check_returncode()
    subprocess.run(
        ["spack", "-D", local_env_dir, "concretize"], capture_output=True
    ).check_returncode()

    update(project_config, status="concretized")

    env = ev.Environment(local_env_dir)
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
    result = subprocess.run(
        f"spack env activate {local_env_dir}; spack install -j{ncores}", shell=True
    )

    if result.returncode == 0:
        print()
        update(project_config, status="ready")
        tty.msg(
            f"{bold(name)} is ready for development " f"(e.g type {cyan('spack mpd build ...')})\n"
        )
