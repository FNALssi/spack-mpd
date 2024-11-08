import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from ruamel.yaml.scalarstring import SingleQuotedScalarString as YamlQuote

import llnl.util.tty as tty

import spack.compilers as compilers
import spack.environment as ev
import spack.store
from spack import traverse
from spack.repo import PATH
from spack.spec import InstallStatus, Spec

from .config import mpd_project_exists, project_config_from_args, selected_projects_dir, update
from .preconditions import State, preconditions
from .util import bold, cyan, get_number, gray, make_yaml_file

SUBCOMMAND = "new-project"
ALIASES = ["n", "newDev"]


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


def cmake_develop(project_config):
    project_name = project_config["name"]
    source_path = Path(project_config["source"])
    file_dir = Path(__file__).resolve().parent
    with open((source_path / "develop.cmake").absolute(), "w") as out:
        out.write(f"""set(CWD "{file_dir}")
macro(develop pkg)
  install(CODE "execute_process(COMMAND spack python ensure-install-directory.py\\
                                        {project_name} ${{${{pkg}}_HASH}}\\
                                WORKING_DIRECTORY ${{CWD}})")
  install(CODE "set(CMAKE_INSTALL_PREFIX ${{${{pkg}}_INSTALL_PREFIX}})")
  add_subdirectory(${{pkg}})
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
    cxx_standard = project_config["cxxstd"]
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


def make_cmake_files(project_config, dependencies, view_path):
    cmake_develop(project_config)
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
    # We use the following sorting algorithm:
    #
    #  0. Form a dictionary of package name to its list of dependencies that are developed.
    #  1. In the package dependencies dictionary, find the packages with no listed dependencies.
    #  2. Place that package name at the front of the ordered-dependency list
    #  3. Remove the package name from the other packages' dependency lists
    #  4. Remove the package from the package dependencies dictionary.
    #  5. Repeat steps 1-4 until there are no more changes to the package-dependencies dictionary.
    pkg_dependencies = {}
    install_prefixes = {}
    for s in env.all_specs():
        if s.name not in package_requirements:
            continue
        ds = []
        for _, d in traverse.traverse_tree([s], depth_first=False):
            if d.spec.name not in package_requirements:
                continue
            if d.spec.name == s.name:
                continue
            ds.append(d.spec.name)
        pkg_dependencies[s.name] = ds
        install_prefixes[s.name] = (s.name, s.dag_hash(), s.prefix)

    ordered_dependencies = []
    size = len(pkg_dependencies) + 1
    while (size != len(pkg_dependencies)):
        to_remove = []
        for k, vs1 in pkg_dependencies.items():
            if len(vs1) != 0:
                continue

            to_remove.append(k)
            ordered_dependencies.append(install_prefixes[k])
            for vs2 in pkg_dependencies.values():
                if k not in vs2:
                    continue
                vs2.remove(k)

        size = len(pkg_dependencies)
        for k in to_remove:
            del pkg_dependencies[k]

    return ordered_dependencies


def process_config(package_requirements, project_config, yes_to_all):
    proto_envs = [ev.read(name) for name in project_config["envs"]]

    print()
    tty.msg(cyan("Determining dependencies") + " (this may take a few minutes)")

    name = project_config["name"]

    # # If the compiler has been installed via Spack, in can be included as a spec in the
    # # environment configuration.  This makes it possible to use (e.g.) g++ directly within
    # # the environment without having to specify the full path to CMake.
    compiler = compilers.find(project_config["compiler"])[0]
    compiler_str = [YamlQuote(compiler)]

    reuse_block = {"from": [{"type": "local"}, {"type": "external"}]}
    full_block = dict(
        include_concrete=[penv.path for penv in proto_envs],
        definitions=[dict(compiler=compiler_str)],
        specs=list(package_requirements.keys()),
        concretizer=dict(unify=True, reuse=reuse_block),
        packages=package_requirements,
    )

    local_env_dir = project_config["local"]

    # Always start fresh
    env_file = make_yaml_file(
        name, dict(spack=full_block), prefix=local_env_dir, overwrite=True
    )

    tty.info(gray("Creating initial environment"))
    if ev.exists(name):
        ev.read(name).destroy()
    env = ev.create(name, init_file=env_file)
    update(project_config, status="created")

    tty.info(gray("Concretizing initial environment"))
    with env, env.write_transaction():
        env.concretize()
        env.write(regenerate=False)

    # Create properly ordered CMake file
    make_cmake_files(project_config,
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
            first_order_deps[dep.name] = dep.format("{name}{@version}"
                                                    "{%compiler.name}{@compiler.version}{compiler_flags}"
                                                    "{variants}")

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

    msg = "Ready to install development environment for " + bold(name) + "\n"

    if absent_dependencies:
        # Remove duplicates, preserving order
        unique_absent_dependencies = []
        for dep in absent_dependencies:
            if dep not in unique_absent_dependencies:
                unique_absent_dependencies.append(dep)
        absent_dependencies = unique_absent_dependencies

        def _parens_number(i):
            return f"({i})"

        msg += "\nThe following packages will be installed:\n"
        width = len(_parens_number(len(absent_dependencies)))
        for i, dep in enumerate(sorted(absent_dependencies)):
            num_str = _parens_number(i + 1)
            msg += f"\n {num_str:>{width}}  {dep}"
        msg += "\n\nPlease ensure you have adequate space for these installations.\n"
    tty.msg(msg)

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
        msg = (
            f"The development environment for {bold(name)} is ready.  "
            f"To activate it, invoke:\n\n  spack env activate {local_env_dir}\n"
        )
        tty.msg(msg)


def print_config_info(config):
    print(f"\nUsing {cyan('build')} area: {config['build']}")
    print(f"Using {cyan('local')} area: {config['local']}")
    print(f"Using {cyan('sources')} area: {config['source']}\n")
    packages = config["packages"]
    if not packages:
        return

    print("  Will develop:")
    for p in packages:
        print(f"    - {p}")


def prepare_project(project_config):
    for d in ("top", "build", "local", "source"):
        Path(project_config[d]).mkdir(exist_ok=True)


def concretize_project(project_config, yes_to_all):
    packages_to_develop = project_config["packages"]

    cxxstd = project_config["cxxstd"]
    package_requirements = {}
    for p in packages_to_develop:
        # Check to see if packages support a 'cxxstd' variant
        spec = Spec(p)
        pkg_cls = PATH.get_pkg_class(spec.name)
        pkg = pkg_cls(spec)
        pkg_requirements = ["@develop", f"%{project_config['compiler']}"]
        maybe_has_variant = getattr(pkg, "has_variant", lambda _: False)
        if maybe_has_variant("cxxstd") or "cxxstd" in pkg.variants:
            pkg_requirements.append(f"cxxstd={cxxstd}")
        package_requirements[spec.name] = dict(require=[YamlQuote(s) for s in pkg_requirements])

    dependencies_to_add = project_config["variants"].split("^")
    # Always erase the first entry...it either applies to the top-level package, or is empty.
    dependencies_to_add.pop(0)

    process_config(package_requirements, project_config, yes_to_all)


def select(name):
    session_id = os.getsid(os.getpid())
    selected = selected_projects_dir()
    selected.mkdir(exist_ok=True)
    (selected / f"{session_id}").write_text(name)


def refresh_project(name, project_config, yes_to_all):
    print()

    tty.msg(f"Refreshing project: {bold(name)}")
    print_config_info(project_config)

    if not project_config["packages"]:
        tty.msg(
            "No packages to develop.  You can clone repositories for development by invoking\n\n"
            "  spack mpd git-clone --suite <suite name>\n\n"
            "  (or type 'spack mpd git-clone --help' for more options)\n"
        )
        return

    local_env_dir = project_config["local"]
    if ev.is_env_dir(local_env_dir):
        ev.Environment(local_env_dir).destroy()
    prepare_project(project_config)
    concretize_project(project_config, yes_to_all)


def process(args):
    preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)

    print()

    name = args.name
    project_config = project_config_from_args(args)
    if mpd_project_exists(name):
        if args.force:
            tty.info(f"Overwriting existing MPD project {bold(name)}")
            local_env_dir = project_config["local"]
            if ev.is_env_dir(local_env_dir):
                ev.Environment(local_env_dir).destroy()
                tty.info(gray(f"Removed existing environment at {project_config['local']}"))
        else:
            indent = " " * len("==> Error: ")
            tty.die(
                f"An MPD project with the name {bold(name)} already exists.\n"
                f"{indent}Either choose a different name or use the '--force' option"
                " to overwrite the existing project.\n"
            )
    else:
        tty.msg(f"Creating project: {bold(name)}")

    update(project_config, status="(none)")

    print_config_info(project_config)
    prepare_project(project_config)
    select(project_config["name"])

    if len(project_config["packages"]):
        concretize_project(project_config, args.yes_to_all)
    else:
        tty.msg(
            "You can clone repositories for development by invoking\n\n"
            "  spack mpd git-clone --suite <suite name>\n\n"
            "  (or type 'spack mpd git-clone --help' for more options)\n"
        )
