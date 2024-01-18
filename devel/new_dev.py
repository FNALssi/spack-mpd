from spack.spec import Spec
import spack.hash_types as ht
import spack.util.spack_yaml as syaml
import llnl.util.tty as tty


import os
import re
import argparse
import sys
from pathlib import Path


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


def cmake_preamble(package):
    return f"""cmake_minimum_required (VERSION 3.18.2 FATAL_ERROR)
project({package}-devel LANGUAGES NONE)

find_package(cetmodules REQUIRED)
include(CetCMakeEnv)

"""


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


def make_cmake_file(package, dependencies, source_dir):
    with open((source_dir / "CMakeLists.txt").absolute(), "w") as f:
        f.write(cmake_preamble(package))
        for d in dependencies:
            f.write(f"add_subdirectory({d})\n")
        f.write("\nenable_testing()")
        # print(f"Made {f.name} file")


def make_yaml_file(package, spec):
    with open(f"{package}.yaml", "w") as f:
        syaml.dump(spec, stream=f, default_flow_style=False)
        print(f"Made {f.name} file")


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


def make_setup_file(
    package, local_packages_dir, ordered_dependencies, source_path, build_path
):
    setup_file = local_packages_dir / "setup.sh"
    with open(setup_file.absolute(), "w") as f:
        f.write("#!/bin/bash\n\n")
        f.write('alias mrb="spack mrb"\n\n')
        f.write(f"export MRB_SOURCE={source_path.absolute()}\n")
        f.write(f"export MRB_BUILDDIR={build_path.absolute()}\n")
        f.write("local_repo=$(realpath $(dirname ${BASH_SOURCE[0]}))\n")
        f.write("spack repo add --scope=user $local_repo >& /dev/null\n")
        f.write(f"spack load {package}\n\n")
        f.write("trap 'spack repo rm $local_repo' EXIT\n")


def process(name, local_packages_dir, packages_to_develop, sources_path, build_path):
    spec = Spec(name + "-bootstrap@develop")
    bootstrap_name = spec.name

    concretized_spec = spec.concretized()

    ordered_dependencies = [
        p.name
        for p in concretized_spec.traverse(order="topo")
        if p.name in packages_to_develop
    ]
    make_setup_file(
        name,
        local_packages_dir.parents[0],
        ordered_dependencies,
        sources_path,
        build_path,
    )

    ordered_dependencies.reverse()
    make_cmake_file(name, ordered_dependencies, sources_path)

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

    top_level_package["name"] = name
    top_level_package["dependencies"] = list(packages.values())

    # Always replace the bundle file
    deps_for_bundlefile = [
        lint_spec(p) for p in concretized_spec.traverse() if p.name in packages
    ]
    make_bundle_file(name, local_packages_dir, deps_for_bundlefile)

    # final_nodes = [n for n in nodes if n["name"] not in package_names]
    # spec_dict["spec"]["nodes"] = final_nodes
    #
    # make_yaml_file(name, spec_dict)


def new_dev(name, top_dir, source_dir, variants):
    print()

    tty.msg(f"Creating project: {name}")

    sp = Path(source_dir)
    packages_to_develop = [
        f.name for f in sp.iterdir() if not f.name.startswith(".") and f.is_dir()
    ]
    stringized_variants = " ".join(variants)
    packages_at_develop = [
        f"{p}@develop {stringized_variants}".strip() for p in packages_to_develop
    ]

    p = Path(top_dir)
    lp = p / "local"
    local_packages_dir = lp / "packages"
    if not lp.exists():
        lp.mkdir()
        local_packages_dir.mkdir()
        make_spack_repo(name, lp)
        os.system(
            f"spack repo add --scope=user $(realpath {lp.absolute()}) >& /dev/null"
        )

    # Always replace the bootstrap bundle file
    make_bundle_file(name + "-bootstrap", local_packages_dir, packages_at_develop)

    bp = p / "build"
    if not bp.exists():
        bp.mkdir()

    print(f"\nUsing build area: {bp.absolute()}")
    print(f"Using local area: {lp.absolute()}")
    print(f"Using sources area: {sp.absolute()}")
    packages_to_develop.sort()

    print(f"  Will develop:")
    for p in packages_to_develop:
        print(f"    - {p}")

    print()
    tty.msg("Concretizing project (this may take a few minutes)")
    process(name, local_packages_dir, packages_to_develop, sp, bp)
    tty.msg("Concretization complete\n")
    tty.msg(
        tty.color.colorize("@*{To install dependencies, invoke}")
        + f"\n\n  spack install {name}\n"
    )
    tty.msg(
        tty.color.colorize("@*{To setup your user environment, invoke}")
        + f"\n\n  source {lp.absolute()}/setup.sh\n"
    )
