import copy
import json
import os
import subprocess
import time
from pathlib import Path

import ruamel.yaml

import llnl.util.tty as tty

import spack.compilers as compilers
import spack.deptypes as dt
import spack.environment as ev
import spack.hash_types as ht
from spack.repo import PATH
from spack.spec import InstallStatus, Spec

from .config import (
    mpd_config_dir,
    mpd_project_exists,
    project_config_from_args,
    selected_projects_dir,
    update,
)
from .preconditions import State, preconditions
from .util import bold, cyan, get_number, make_yaml_file

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


def entry(package_list, package_name):
    for p in package_list:
        if package_name == p["name"]:
            return p
    return None


def entry_with_index(package_list, package_name):
    for i, p in enumerate(package_list):
        if package_name == p["name"]:
            return i, p
    return None


def cmake_lists_preamble(package):
    date = time.strftime("%Y-%m-%d")
    return f"""cmake_minimum_required (VERSION 3.18.2 FATAL_ERROR)
enable_testing()

project({package}-{date} LANGUAGES NONE)
"""


def cmake_presets(source_path, dependencies, cxx_standard, preset_file):
    configurePresets, cacheVariables = "configurePresets", "cacheVariables"
    allCacheVariables = {
        "CMAKE_BUILD_TYPE": {"type": "STRING", "value": "RelWithDebInfo"},
        "CMAKE_CXX_EXTENSIONS": {"type": "BOOL", "value": "OFF"},
        "CMAKE_CXX_STANDARD_REQUIRED": {"type": "BOOL", "value": "ON"},
        "CMAKE_CXX_STANDARD": {"type": "STRING", "value": cxx_standard},
    }

    # Pull project-specific presets from each dependency.
    for dep in dependencies:
        pkg_presets_file = source_path / dep / "CMakePresets.json"
        if not pkg_presets_file.exists():
            continue

        with open(pkg_presets_file, "r") as f:
            pkg_presets = json.load(f)
            pkg_config_presets = pkg_presets[configurePresets]
            default_presets = next(
                filter(lambda s: s["name"] == "from_product_deps", pkg_config_presets)
            )
            for key, value in default_presets[cacheVariables].items():
                if key.startswith(dep):
                    allCacheVariables[key] = value

    presets = {
        configurePresets: [
            {
                cacheVariables: allCacheVariables,
                "description": "Configuration settings as created by 'spack mpd new-dev'",
                "displayName": "Configuration from mpd new-dev",
                "name": "default",
            }
        ],
        "version": 3,
    }
    return json.dump(presets, preset_file, indent=4)


def bundle_template(package, dependencies):
    camel_package = package.split("-")
    camel_package = "".join(word.title() for word in camel_package)
    bundle_str = f"""from spack.package import *
import spack.extensions


class {camel_package}(BundlePackage):
    "Bundle package for developing {package}"

    homepage = "[See https://...  for instructions]"

    version("develop")

"""
    for dep in dependencies:
        bundle_str += f'    depends_on("{dep}")\n'

    return bundle_str


def make_cmake_file(package, dependencies, project_config):
    source_path = Path(project_config["source"])
    with open((source_path / "CMakeLists.txt").absolute(), "w") as f:
        f.write(cmake_lists_preamble(package))
        for d in dependencies:
            f.write(f"\nadd_subdirectory({d})")

    with open((source_path / "CMakePresets.json").absolute(), "w") as f:
        cmake_presets(source_path, dependencies, project_config["cxxstd"], f)


def make_bundle_file(name, deps, project_config):
    bundle_path = mpd_config_dir() / "packages" / name
    bundle_path.mkdir(exist_ok=True)
    package_recipe = bundle_path / "package.py"
    package_recipe.write_text(bundle_template(name, deps))


def external_config_for_spec(spec):
    external_config = {"spec": spec.short_spec, "prefix": str(spec.prefix)}
    return {"externals": [external_config], "buildable": False}


def process_config(project_config, yes_to_all):
    proto_envs = [ev.read(name) for name in project_config["envs"]]

    print()
    tty.msg(cyan("Concretizing project") + " (this may take a few minutes)")

    name = project_config["name"]
    spec_like = f"{name}-bootstrap@develop {project_config['variants']}"
    spec = Spec(spec_like)

    bootstrap_name = spec.name

    concretized_spec = spec.concretized()

    packages_to_develop = project_config["packages"]
    ordered_dependencies = [
        p.name for p in concretized_spec.traverse(order="topo") if p.name in packages_to_develop
    ]
    ordered_dependencies.reverse()

    make_cmake_file(name, ordered_dependencies, project_config)

    # YAML file
    spec_dict = concretized_spec.to_dict(ht.dag_hash)
    nodes = spec_dict["spec"]["nodes"]

    top_level_package = entry(nodes, bootstrap_name)
    assert top_level_package

    package_names = [dep["name"] for dep in top_level_package["dependencies"]]
    packages = {dep["name"]: dep for dep in top_level_package["dependencies"]}

    for pname in package_names:
        i, p = entry_with_index(nodes, pname)
        assert p

        pdeps = {pdep["name"]: pdep for pdep in p.get("dependencies", [])}
        packages.update(pdeps)
        del nodes[i]

    for pname in packages_to_develop:
        del packages[pname]

    user_specs = set()
    packages_block = {}
    for p in concretized_spec.traverse(deptype=dt.BUILD | dt.RUN):
        if p.name not in packages:
            continue

        # External packages cannot be specs
        if p.install_status() != InstallStatus.external:
            user_specs.add(p.name)

        if any(penv.matching_spec(p) for penv in proto_envs):
            continue

        requires = []
        if version := str(p.version):
            requires.append(f"@{version}")
        if compiler := str(p.compiler):
            requires.append(f"%{compiler}")
        if p.variants:
            variants = copy.deepcopy(p.variants)
            if "patches" in variants:
                del variants["patches"]
            requires.extend(
                ruamel.yaml.scalarstring.SingleQuotedScalarString(s) for s in str(variants).split()
            )
        if compiler_flags := str(p.compiler_flags):
            requires.append(compiler_flags)

        packages_block[p.name] = dict(require=requires)

    # If the compiler has been installed via Spack, in can be included as a spec in the
    # environment configuration.  This makes it possible to use (e.g.) g++ directly within
    # the environment without having to specify the full path to CMake.
    compiler = compilers.find(project_config["compiler"])[0]
    compiler_str = [ruamel.yaml.scalarstring.SingleQuotedScalarString(compiler)]
    cpspec = compilers.pkg_spec_for_compiler(compiler)
    maybe_include_compiler = []
    if cpspec.install_status() == InstallStatus.installed:
        maybe_include_compiler = compiler_str

    full_block = dict(
        include_concrete=[penv.path for penv in proto_envs],
        definitions=[dict(compiler=compiler_str)],
        specs=maybe_include_compiler + list(user_specs),
        concretizer=dict(unify=True, reuse=True),
        packages=packages_block,
    )

    env_file = make_yaml_file(
        name, dict(spack=full_block), prefix=mpd_config_dir(), overwrite=True
    )

    env = ev.create(name, init_file=env_file)
    tty.info(f"Environment {name} has been created")
    update(project_config, status="created")

    with env, env.write_transaction():
        env.concretize()
        env.write()

    absent_dependencies = []
    missing_intermediate_deps = {}
    for n in env.all_specs():
        if n.name == bootstrap_name:
            continue

        if n.install_status() == InstallStatus.absent:
            absent_dependencies.append(n.cshort_spec)

        checked_out_deps = [p.name for p in n.dependencies() if p.name in packages_to_develop]
        if checked_out_deps:
            missing_intermediate_deps[n.name] = checked_out_deps

    if missing_intermediate_deps:
        error_msg = (
            "The following packages are intermediate dependencies of the\n"
            "currently cloned packages and must also be cloned:\n"
        )
        for pkg_name, checked_out_deps in missing_intermediate_deps.items():
            checked_out_deps_str = ", ".join(checked_out_deps)
            error_msg += "\n - " + bold(pkg_name)
            error_msg += f" (depends on {checked_out_deps_str})"
        print()
        tty.die(error_msg + "\n")

    tty.msg(cyan("Concretization complete\n"))
    update(project_config, status="concretized")

    msg = "Ready to install MPD project " + bold(name) + "\n"

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
        should_install = tty.get_yes_or_no(
            "Would you like to continue with installation?", default=True
        )
    else:
        should_install = True

    if should_install is False:
        print()
        tty.msg(
            f"To install {name} later, invoke:\n\n" + f"  spack -e {name} install -j<ncores>\n"
        )
        return

    if not yes_to_all:
        ncores = get_number("Specify number of cores to use", default=os.cpu_count() // 2)
    else:
        ncores = os.cpu_count() // 2

    tty.msg(f"Installing {name}")
    result = subprocess.run(["spack", "-e", name, "install", f"-j{ncores}"])

    if result.returncode == 0:
        print()
        update(project_config, status="installed")
        msg = (
            f"MPD project {bold(name)} has been installed.  "
            f"To load it, invoke:\n\n  spack env activate {name}\n"
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
    for d in ("top", "build", "local", "install", "source"):
        Path(project_config[d]).mkdir(exist_ok=True)


def concretize_project(project_config, yes_to_all):
    packages_to_develop = project_config["packages"]

    # Always replace the bootstrap bundle file
    cxxstd = project_config["cxxstd"]
    packages_at_develop = []
    for p in packages_to_develop:
        # Check to see if packages support a 'cxxstd' variant
        spec = Spec(p)
        pkg_cls = PATH.get_pkg_class(spec.name)
        pkg = pkg_cls(spec)
        base_spec = f"{p}@develop %{project_config['compiler']}"
        if "cxxstd" in pkg.variants:
            base_spec += f" cxxstd={cxxstd}"
        packages_at_develop.append(base_spec)

    dependencies_to_add = project_config["variants"].split("^")
    # Always erase the first entry...it either applies to the top-level package, or is emtpy.
    dependencies_to_add.pop(0)

    packages_at_develop.extend(dependencies_to_add)

    make_bundle_file(project_config["name"] + "-bootstrap", packages_at_develop, project_config)

    process_config(project_config, yes_to_all)


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

    if ev.exists(name):
        ev.read(name).destroy()
    concretize_project(project_config, yes_to_all)


def process(args):
    preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)

    print()

    name = args.name
    if mpd_project_exists(name):
        if args.force:
            tty.info(f"Overwriting existing MPD project {bold(name)}")
            if ev.exists(name):
                ev.read(name).destroy()
                tty.info(f"Existing environment {name} has been removed")
        else:
            indent = " " * len("==> Error: ")
            tty.die(
                f"An MPD project with the name {bold(name)} already exists.\n"
                f"{indent}Either choose a different name or use the '--force' option"
                " to overwrite the existing project.\n"
            )
    else:
        tty.msg(f"Creating project: {bold(name)}")

    project_config = project_config_from_args(args)
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
