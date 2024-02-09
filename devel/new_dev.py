import argparse
import json
import os
import re
import sys
from pathlib import Path

import llnl.util.tty as tty

import spack.hash_types as ht
import spack.util.spack_yaml as syaml
from spack.spec import Spec


def lint_spec(spec):
    spec_str = spec.short_spec
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


def cmake_lists_preamble(package):
    return f"""cmake_minimum_required (VERSION 3.18.2 FATAL_ERROR)
project({package}-devel LANGUAGES NONE)

find_package(cetmodules REQUIRED)
include(CetCMakeEnv)

"""


def cmake_presets(source_dir, dependencies, cxx_standard, preset_file):
    configurePresets, cacheVariables = "configurePresets", "cacheVariables"
    allCacheVariables = {
        "CMAKE_BUILD_TYPE": {"type": "STRING", "value": "RelWithDebInfo"},
        "CMAKE_CXX_EXTENSIONS": {"type": "BOOL", "value": "OFF"},
        "CMAKE_CXX_STANDARD_REQUIRED": {"type": "BOOL", "value": "ON"},
        "CMAKE_CXX_STANDARD": {"type": "STRING", "value": cxx_standard},
    }

    # Pull project-specific presets from each dependency.
    for dep in dependencies:
        pkg_presets_file = source_dir / dep / "CMakePresets.json"
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


class {camel_package}(BundlePackage):
    "Bundle package for developing {package}"

    homepage = "[See https://...  for instructions]"

    version("develop")

"""
    for dep in dependencies:
        bundle_str += f'    depends_on("{dep}")\n'

    return bundle_str


def make_cmake_file(package, dependencies, source_dir, cxx_standard):
    with open((source_dir / "CMakeLists.txt").absolute(), "w") as f:
        f.write(cmake_lists_preamble(package))
        for d in dependencies:
            f.write(f"add_subdirectory({d})\n")
        f.write("\nenable_testing()")

    with open((source_dir / "CMakePresets.json").absolute(), "w") as f:
        cmake_presets(source_dir, dependencies, cxx_standard, f)


def make_yaml_file(package, spec):
    with open(f"{package}.yaml", "w") as f:
        syaml.dump(spec, stream=f, default_flow_style=False)


def make_bundle_file(name, local_packages_dir, deps):
    bundle_dir = local_packages_dir / name
    bundle_dir.mkdir(exist_ok=True)
    package_recipe = bundle_dir / "package.py"
    with open(package_recipe.absolute(), "w") as f:
        f.write(bundle_template(name, deps))


def make_spack_repo(package, local_packages_dir):
    repo_file = local_packages_dir / "repo.yaml"
    with open(repo_file.absolute(), "w") as f:
        f.write("repo:\n")
        f.write(
            f"  namespace: '{package}'\n"
        )  # Not sure that we want the repo name to be this specific


def make_bare_setup_file(local_dir, source_path, build_path):
    setup_file = local_dir / "setup.sh"
    install = local_dir / "install"
    with open(setup_file.absolute(), "w") as f:
        f.write("#!/bin/bash\n\n")
        f.write('alias mrb="spack mrb"\n\n')
        f.write(f"export MRB_SOURCE={source_path.absolute()}\n")
        f.write(f"export MRB_BUILDDIR={build_path.absolute()}\n")
        f.write(f"export MRB_LOCAL={local_dir.absolute()}\n")
        f.write(f"export MRB_INSTALL={install.absolute()}\n")


def make_setup_file(package, compiler, local_dir, source_path, build_path):
    setup_file = local_dir / "setup.sh"
    install = local_dir / "install"
    with open(setup_file.absolute(), "w") as f:
        f.write("#!/bin/bash\n\n")
        f.write('alias mrb="spack mrb"\n\n')
        f.write(f"export MRB_SOURCE={source_path.absolute()}\n")
        f.write(f"export MRB_BUILDDIR={build_path.absolute()}\n")
        f.write(f"export MRB_LOCAL={local_dir.absolute()}\n")
        f.write(f"export MRB_INSTALL={install.absolute()}\n\n")
        f.write("local_repo=$(realpath $(dirname ${BASH_SOURCE[0]}))\n")
        f.write("spack repo add --scope=user $local_repo >& /dev/null\n")
        f.write(f"spack load {package}\n")
        if compiler:
            f.write(f"spack load {compiler}\n")
        f.write("\ntrap 'spack repo rm $local_repo' EXIT\n")


def process(
    name, local_packages_dir, packages_to_develop, sources_path, build_path, cxx_standard, variants
):
    spec_like = name + "-bootstrap@develop" + " ".join(variants)
    spec = Spec(spec_like)

    bootstrap_name = spec.name

    concretized_spec = spec.concretized()

    make_setup_file(
        name, concretized_spec.compiler, local_packages_dir.parents[0], sources_path, build_path
    )

    ordered_dependencies = [
        p.name for p in concretized_spec.traverse(order="topo") if p.name in packages_to_develop
    ]
    ordered_dependencies.reverse()
    make_cmake_file(name, ordered_dependencies, sources_path, cxx_standard)

    # YAML file
    spec_dict = concretized_spec.to_dict(ht.dag_hash)
    nodes = spec_dict["spec"]["nodes"]

    top_level_package = entry(nodes, bootstrap_name)
    assert top_level_package

    package_names = [dep["name"] for dep in top_level_package["dependencies"]]
    packages = {dep["name"]: dep for dep in top_level_package["dependencies"]}

    for pname in package_names:
        p = entry(nodes, pname)
        assert p

        pdeps = {pdep["name"]: pdep for pdep in p["dependencies"]}
        packages.update(pdeps)

    for pname in package_names:
        del packages[pname]

    # Always replace the bundle file
    deps_for_bundlefile = [lint_spec(p) for p in concretized_spec.traverse() if p.name in packages]
    make_bundle_file(name, local_packages_dir, deps_for_bundlefile)

    final_nodes = [n for n in nodes if n["name"] not in package_names]
    missing_intermediate_deps = {}
    for n in final_nodes:
        if n["name"] == bootstrap_name:
            continue

        missing_deps = [
            p["name"] for p in n.get("dependencies", []) if p["name"] in packages_to_develop
        ]
        if missing_deps:
            missing_intermediate_deps[n["name"]] = missing_deps

    if missing_intermediate_deps:
        error_msg = "The following packages are intermediate dependencies and must also be checked out:\n\n"
        for pkg_name, missing_deps in missing_intermediate_deps.items():
            missing_deps_str = ", ".join(missing_deps)
            error_msg += "      - " + tty.color.colorize("@*{" + pkg_name + "}")
            error_msg += f" (depends on {missing_deps_str})\n"

        print()
        tty.error(error_msg)
        print()
        sys.exit(1)

    # spec_dict["spec"]["nodes"] = final_nodes
    #
    # make_yaml_file(name, spec_dict)


def new_dev(name, top_dir, source_dir, variants):
    print()

    tty.msg(f"Creating project: {name}")

    bp = top_dir / "build"
    print(f"\nUsing build area: {bp.absolute()}")
    bp.mkdir(exist_ok=True)

    lp = top_dir / "local"
    print(f"Using local area: {lp.absolute()}")
    local_packages_dir = lp / "packages"
    local_install_dir = lp / "install"
    if not lp.exists():
        lp.mkdir()
        local_packages_dir.mkdir()
        make_spack_repo(name, lp)
        os.system(f"spack repo add --scope=user $(realpath {lp.absolute()}) >& /dev/null")
    local_install_dir = lp / "install"
    local_install_dir.mkdir(exist_ok=True)

    sp = Path(source_dir) if source_dir else top_dir / "srcs"
    print(f"Using sources area: {sp.absolute()}")
    sp.mkdir(exist_ok=True)

    # Get C++ standard
    cxx_standard = "17"  # Must be a string for CMake
    cxxstd_index = None
    for i, variant in enumerate(variants):
        match = re.fullmatch("cxxstd=(\d{2})", variant)
        if match:
            cxx_standard = match[1]
            cxxstd_index = i

    # Remove cxxstd variant
    if cxxstd_index is not None:
        del variants[cxxstd_index]

    packages_to_develop = sorted(
        f.name for f in sp.iterdir() if not f.name.startswith(".") and f.is_dir()
    )

    if packages_to_develop:
        print(f"  Will develop:")
        for p in packages_to_develop:
            print(f"    - {p}")

        # Always replace the bootstrap bundle file
        packages_at_develop = [f"{p}@develop" for p in packages_to_develop]
        make_bundle_file(name + "-bootstrap", local_packages_dir, packages_at_develop)

        print()
        tty.msg("Concretizing project (this may take a few minutes)")
        process(name, local_packages_dir, packages_to_develop, sp, bp, cxx_standard, variants)
        tty.msg("Concretization complete\n")
        tty.msg(
            tty.color.colorize("@*{To install dependencies, invoke}")
            + f"\n\n  spack install {name}\n"
        )

        tty.msg(
            tty.color.colorize("@*{To setup your user environment, invoke}")
            + f"\n\n  source {lp.absolute()}/setup.sh\n"
        )
    else:
        print()
        make_bare_setup_file(local_packages_dir.parents[0], sp, bp)
        tty.msg(
            tty.color.colorize("@*{To setup your user environment, invoke}")
            + f"\n\n  source {lp.absolute()}/setup.sh\n"
        )
        tty.msg(
            tty.color.colorize("@*{You can then clone repositories for development by invoking}")
            + f"\n\n  spack mrb g --suite <suite name>\n\n"
            "  (or type 'spack mrb g --help' for more options)\n"
        )
