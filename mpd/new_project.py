import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import ruamel.yaml

import llnl.util.tty as tty

import spack.deptypes as dt
import spack.environment as ev
import spack.hash_types as ht
import spack.util.spack_yaml as syaml
from spack.repo import PATH
from spack.spec import InstallStatus, Spec

from .config import mpd_project_exists, project_config_from_args, update, user_config_dir
from .preconditions import State, preconditions
from .util import bold

SUBCOMMAND = "new-project"
ALIASES = ["n", "newDev"]


def get_number(prompt, **kwargs):
    default = kwargs.get("default", None)
    abort = kwargs.get("abort", None)

    if default is not None and abort is not None:
        prompt += " (default is %s, %s to abort) " % (default, abort)
    elif default is not None:
        prompt += " (default is %s) " % default
    elif abort is not None:
        prompt += " (%s to abort) " % abort

    number = None
    while number is None:
        tty.msg(prompt, newline=False)
        ans = input()
        if ans == str(abort):
            return None

        if ans:
            try:
                number = int(ans)
                if number < 1:
                    tty.msg("Please enter a valid number.")
                    number = None
            except ValueError:
                tty.msg("Please enter a valid number.")
        elif default is not None:
            number = default
    return number


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


def make_yaml_file(package, spec, prefix=None, overwrite=False):
    filepath = Path(f"{package}.yaml")
    if prefix:
        filepath = prefix / filepath
    if filepath.exists() and not overwrite:
        return str(filepath)
    with open(filepath, "w") as f:
        syaml.dump(spec, stream=f, default_flow_style=False)
    return str(filepath)


def make_bundle_file(name, deps, project_config):
    bundle_path = user_config_dir() / "packages" / name
    bundle_path.mkdir(exist_ok=True)
    package_recipe = bundle_path / "package.py"
    package_recipe.write_text(bundle_template(name, deps))


def external_config_for_spec(spec):
    external_config = {"spec": spec.short_spec, "prefix": str(spec.prefix), "buildable": False}
    return {"externals": [external_config]}


def ensure_proto_env_package_files(proto_envs):
    filenames = []
    for penv in proto_envs:
        package_list = {pkg.name: external_config_for_spec(pkg) for pkg in penv.all_specs()}

        # Don't forget the 'all' stanza
        all_config = penv.manifest.configuration.get("packages", {}).get("all", {})
        if all_config:
            package_list["all"] = all_config

        penv_packages_config = dict(packages=package_list)
        filenames.append(
            make_yaml_file(
                f"{penv.name}-packages-config", penv_packages_config, prefix=user_config_dir()
            )
        )

    return filenames


def process_config(project_config):
    proto_envs = [ev.read(name) for name in project_config["envs"]]
    proto_env_packages_files = ensure_proto_env_package_files(proto_envs)

    print()
    tty.msg("Concretizing project (this may take a few minutes)")

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

    # Prepend compiler
    full_block = dict(
        include=proto_env_packages_files,
        definitions=[dict(compiler=[project_config["compiler"]])],
        specs=[project_config["compiler"]] + list(user_specs),
        concretizer=dict(unify=True, reuse=True),
        packages=packages_block,
    )

    env_file = make_yaml_file(
        name, dict(spack=full_block), prefix=user_config_dir(), overwrite=True
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

    tty.msg("Concretization complete\n")
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
        for i, dep in enumerate(absent_dependencies):
            num_str = _parens_number(i + 1)
            msg += f"\n {num_str:>{width}}  {dep}"
        msg += "\n\nPlease ensure you have adequate space for these installations.\n"
    tty.msg(msg)

    should_install = tty.get_yes_or_no(
        "Would you like to continue with installation?", default=True
    )

    if should_install is False:
        print()
        tty.msg(
            f"To install {name} later, invoke:\n\n" + f"  spack -e {name} install -j<ncores>\n"
        )
        return

    ncores = get_number("Specify number of cores to use", default=os.cpu_count() // 2)

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
    print(f"\nUsing build area: {config['build']}")
    print(f"Using local area: {config['local']}")
    print(f"Using sources area: {config['source']}\n")
    packages = config["packages"]
    if not packages:
        return

    print("  Will develop:")
    for p in packages:
        print(f"    - {p}")


def prepare_project(project_config):
    for d in ("top", "build", "local", "install", "source"):
        Path(project_config[d]).mkdir(exist_ok=True)


def concretize_project(project_config):
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

    process_config(project_config)


def declare_active(name):
    session_id = os.getsid(os.getpid())
    active = Path(user_config_dir() / "active")
    active.mkdir(exist_ok=True)
    (active / f"{session_id}").write_text(name)


def refresh_project(name, project_config):
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
        proto_envs = [ev.read(name) for name in project_config["envs"]]
        ensure_proto_env_package_files(proto_envs)
        ev.read(name).destroy()
    concretize_project(project_config)


def process(args):
    preconditions(State.INITIALIZED, ~State.ACTIVE_ENVIRONMENT)

    print()

    name = args.name
    if mpd_project_exists(name):
        if args.force:
            tty.warn(f"Overwriting existing MPD project {bold(name)}")
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
        tty.msg(f"Creating project: {name}")

    project_config = project_config_from_args(args)
    update(project_config, status="(none)")

    print_config_info(project_config)
    prepare_project(project_config)
    declare_active(project_config["name"])

    if len(project_config["packages"]):
        concretize_project(project_config)
    else:
        tty.msg(
            "You can clone repositories for development by invoking\n\n"
            "  spack mpd git-clone --suite <suite name>\n\n"
            "  (or type 'spack mpd git-clone --help' for more options)\n"
        )
