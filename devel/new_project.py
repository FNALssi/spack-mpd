import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import llnl.util.tty as tty

import spack.environment as ev
import spack.hash_types as ht
import spack.util.spack_yaml as syaml
from spack.repo import PATH
from spack.spec import InstallStatus, Spec
from spack.traverse import traverse_nodes

from .mrb_config import mrb_local_dir
from .util import bold


def lint_spec(spec):
    spec_str = spec.short_spec
    spec_str = re.sub(f"@{spec.version}", "", spec_str)  # remove version
    spec_str = re.sub(f"arch={spec.architecture}", "", spec_str)  # remove arch
    spec_str = re.sub(f"%{spec.compiler.display_str}", "", spec_str)  # remove compiler
    spec_str = re.sub(f"/[a-z0-9]+", "", spec_str)  # remove hash
    if "patches" in spec.variants:  # remove patches if present
        spec_str = re.sub(f"{spec.variants['patches']}", "", spec_str)
    return spec_str.strip()


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
    return f"""cmake_minimum_required (VERSION 3.18.2 FATAL_ERROR)
project({package}-devel LANGUAGES NONE)

find_package(cetmodules REQUIRED)
include(CetCMakeEnv)

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
                "description": "Configuration settings as created by 'spack mrb new-dev'",
                "displayName": "Configuration from mrb new-dev",
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
            f.write(f"add_subdirectory({d})\n")
        f.write("\nenable_testing()")

    with open((source_path / "CMakePresets.json").absolute(), "w") as f:
        cmake_presets(source_path, dependencies, project_config["cxxstd"], f)


def make_yaml_file(package, spec, prefix=None):
    filepath = Path(f"{package}.yaml")
    if prefix:
        filepath = prefix / filepath
    with open(filepath, "w") as f:
        syaml.dump(spec, stream=f, default_flow_style=False)
    return str(filepath)


def mrb_envs(name, project_config):
    return f"""

    def setup_run_environment(self, env):
        env.set("MRB_PROJECT", "{name}")
        env.set("MRB_SOURCE", "{project_config['source']}")
        env.set("MRB_BUILDDIR", "{project_config['build']}")
        env.set("MRB_LOCAL", "{project_config['local']}")
        env.set("MRB_INSTALL", "{project_config['install']}")

    @run_after("install")
    def post_install(self):
        mrb = spack.extensions.get_module("mrb")
        mrb.add_project("{name}",
                        "{project_config['top']}",
                        "{project_config['source']}",
                        "cxxstd={project_config['cxxstd']} %{project_config['compiler']} {project_config['variants']}")
"""
    # FIXME: Should replace the above "variants" string with something safer...like the variants actually presented at command-line


def make_bundle_file(name, deps, project_config, include_mrb_envs=False):
    bundle_path = mrb_local_dir() / "packages" / name
    bundle_path.mkdir(exist_ok=True)
    package_recipe = bundle_path / "package.py"
    with open(package_recipe.absolute(), "w") as f:
        f.write(bundle_template(name, deps))
        if include_mrb_envs:
            f.write(mrb_envs(name, project_config))


def make_bare_setup_file(name, project_config):
    setup_file = Path(project_config["local"]) / "setup.sh"
    with open(setup_file.absolute(), "w") as f:
        f.write("#!/bin/bash\n\n")
        f.write('alias mrb="spack mrb"\n\n')


def make_setup_file(name, compiler, project_config):
    setup_file = Path(project_config["local"]) / "setup.sh"
    with open(setup_file.absolute(), "w") as f:
        f.write("#!/bin/bash\n\n")
        f.write('alias mrb="spack mrb"\n\n')
        f.write(f"spack load {name}\n")
        if compiler:
            f.write(f"spack load {compiler}\n")


def process(name, from_env, project_config):
    # What happens if there's no environment?
    proto_env = ev.read(from_env)
    proto_env_packages_config = dict(packages=proto_env.manifest.configuration.get("packages", {}))
    proto_env_packages_file = make_yaml_file(
        f"{from_env}-packages-config", proto_env_packages_config, prefix=mrb_local_dir()
    )

    print()
    tty.msg("Concretizing project (this may take a few minutes)")
    spec_like = (
        f"{name}-bootstrap@develop %{project_config['compiler']} {project_config['variants']}"
    )
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

        pdeps = {pdep["name"]: pdep for pdep in p["dependencies"]}
        packages.update(pdeps)
        del nodes[i]

    for pname in package_names:
        del packages[pname]

    deps_for_bundlefile = []
    packages_block = {}
    for p in concretized_spec.traverse():
        if p.name not in packages:
            continue

        deps_for_bundlefile.append(p.name)

        if proto_env.matching_spec(p):
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
            requires.extend(str(variants).split())
        if compiler_flags := str(p.compiler_flags):
            requires.append(compiler_flags)

        packages_block[p.name] = dict(require=requires)

    # Always replace the bundle file
    mrb_name = name + "-mrb"
    make_bundle_file(mrb_name, deps_for_bundlefile, project_config, include_mrb_envs=True)

    concretizer = dict(unify=True, reuse=True)
    full_block = dict(
        include=[proto_env_packages_file],
        definitions=[dict(compiler=[project_config["compiler"]])],
        specs=[project_config["compiler"], mrb_name],
        concretizer=dict(unify=True, reuse=True),
        packages=packages_block,
    )

    env_file = make_yaml_file(name, dict(spack=full_block), prefix=mrb_local_dir())
    env = ev.create(name, init_file=env_file)

    concretized_specs = None
    with env.write_transaction():
        concretized_specs = env.concretize()
        env.write()

    absent_dependencies = []
    missing_intermediate_deps = {}
    for n in traverse_nodes([p[1] for p in concretized_specs], order="post"):
        if n.name == bootstrap_name:
            continue

        if n.install_status() == InstallStatus.absent:
            absent_dependencies.append(n.cshort_spec)

        missing_deps = [p.name for p in n.dependencies() if p.name in packages_to_develop]
        if missing_deps:
            missing_intermediate_deps[n.name] = missing_deps

    if missing_intermediate_deps:
        error_msg = "\nThe following packages are intermediate dependencies and must also be checked out:\n\n"
        for pkg_name, missing_deps in missing_intermediate_deps.items():
            missing_deps_str = ", ".join(missing_deps)
            error_msg += "      - " + bold(pkg_name)
            error_msg += f" (depends on {missing_deps_str})\n"
        error_msg += "\n"
        tty.die(error_msg)

    tty.msg("Concretization complete\n")

    msg = "Ready to install MRB project " + bold(name) + "\n"
    if absent_dependencies:

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
            f"To install {name} later, invoke:\n\n"
            + bold(f"  spack -e {name} install -j<ncores>\n")
        )
        return

    ncores = tty.get_number("Specify number of cores to use", default=os.cpu_count() // 2)

    tty.msg(f"Installing {name}")
    result = subprocess.run(["spack", "-e", name, "install", f"-j{ncores}"])

    if result.returncode == 0:
        print()
        msg = f"MRB project {bold(name)} has been installed.  To load it, invoke:\n\n  spack env activate {name}\n"
        tty.msg(msg)


def print_config_info(config):
    print(f"\nUsing build area: {config['build']}")
    print(f"Using local area: {config['local']}")
    print(f"Using sources area: {config['source']}\n")
    packages = config["packages"]
    if not packages:
        return

    print(f"  Will develop:")
    for p in packages:
        print(f"    - {p}")


def prepare_project(name, project_config):
    build_dir = project_config["build"]
    bp = Path(build_dir)
    bp.mkdir(exist_ok=True)

    local_dir = project_config["local"]
    lp = Path(local_dir)
    lp.mkdir(exist_ok=True)

    local_install_path = Path(project_config["install"])
    local_install_path.mkdir(exist_ok=True)

    source_dir = project_config["source"]
    sp = Path(source_dir)
    sp.mkdir(exist_ok=True)


def concretize_project(name, from_env, project_config):
    packages_to_develop = project_config["packages"]

    # Always replace the bootstrap bundle file
    cxxstd = project_config["cxxstd"]
    packages_at_develop = []
    for p in packages_to_develop:
        # Check to see if packages support a 'cxxstd' variant
        spec = Spec(p)
        pkg_cls = PATH.get_pkg_class(spec.name)
        pkg = pkg_cls(spec)
        base_spec = f"{p}@develop"
        if "cxxstd" in pkg.variants:
            base_spec += f" cxxstd={cxxstd}"
        packages_at_develop.append(base_spec)

    make_bundle_file(name + "-bootstrap", packages_at_develop, project_config)

    process(name, from_env, project_config)


def new_project(name, from_env, project_config):
    print()
    tty.msg(f"Creating project: {name}")
    print_config_info(project_config)

    prepare_project(name, project_config)

    if len(project_config["packages"]):
        concretize_project(name, from_env, project_config)
    else:
        make_bare_setup_file(name, project_config)
        tty.msg(
            bold("To setup your user environment, invoke")
            + f"\n\n  source {project_config['local']}/setup.sh\n"
        )
        tty.msg(
            bold("You can then clone repositories for development by invoking")
            + f"\n\n  spack mrb g --suite <suite name>\n\n"
            "  (or type 'spack mrb g --help' for more options)\n"
        )


def update_project(name, project_config):
    print()

    tty.msg(f"Updating project: {name}")
    print_config_info(project_config)

    if not project_config["packages"]:
        tty.msg(
            bold("No packages to develop.  You can clone repositories for development by invoking")
            + f"\n\n  spack mrb g --suite <suite name>\n\n"
            "  (or type 'spack mrb g --help' for more options)\n"
        )
        return

    concretize_project(name, project_config)
