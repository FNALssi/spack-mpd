import subprocess
from pathlib import Path

import spack.llnl.util.tty as tty

from .config import selected_project_config
from .preconditions import State, activate_development_environment, preconditions
from .util import cyan, remove_dir

SUBCOMMAND = "build"
ALIASES = ["b"]


def setup_subparser(subparsers):
    build = subparsers.add_parser(
        SUBCOMMAND,
        description="build repositories under development",
        aliases=ALIASES,
        help="build repositories",
    )
    build.add_argument("--clean", action="store_true", help="clean build area before building")
    build.add_argument(
        "--configure-only", action="store_true", help="run CMake configuration only, do not build"
    )
    build.add_argument(
        "-j",
        dest="parallel",
        metavar="<number>",
        help="specify number of threads for parallel build",
    )
    build.add_argument(
        "-D",
        "--define-variable",
        dest="cmake_defines",
        action="append",
        help="CMake variable definition (e.g. -DFOO:STRING=bar)",
        metavar="<var>:<type>=<value>",
    )
    build.add_argument(
        "--packages",
        nargs="+",
        metavar="<package>",
        help="build only targets for the specified checked-out packages",
    )
    build.add_argument(
        "generator_options",
        metavar="-- <generator options>",
        nargs="*",
        help="options passed directly to generator",
    )


def _generator_value(project_config):
    value = project_config["generator"]["value"]
    if value == "make":
        return "Unix Makefiles"
    if value == "ninja":
        return "Ninja"
    tty.die(f"Only 'make' and 'ninja' generators are allowed (specified {value}).")


def configure_cmake_project(project_config, cmake_defines=None):
    configure_list = [
        "cmake",
        "--preset",
        "default",
        project_config["source"],
        "-B",
        project_config["build"],
        "-G",
        _generator_value(project_config),
    ]

    if cmake_defines:
        configure_list.extend([f"-D{define}" for define in cmake_defines])

    printed_configure_list = []
    for arg in configure_list:
        if arg.count(" ") > 0:
            printed_configure_list.append(f'"{arg}"')
        else:
            printed_configure_list.append(arg)

    configure_list_str = " ".join(printed_configure_list)
    print()
    tty.msg("Configuring with command:\n\n" + cyan(configure_list_str) + "\n")

    return subprocess.run(configure_list)


def configure(project_config, cmake_defines=None):
    result = configure_cmake_project(project_config, cmake_defines)
    if result.returncode != 0:
        print()
        tty.die("The CMake configure step failed. See above\n")


def source_directories(project_config):
    source_path = Path(project_config["source"])
    return sorted(f.name for f in source_path.iterdir() if not f.name.startswith(".") and f.is_dir())


def package_directory_target(project_config, package_source_directory):
    generator = project_config["generator"]["value"]
    if generator in ("ninja", "make"):
        return f"{package_source_directory}/all"

    tty.die(f"Only 'make' and 'ninja' generators are allowed (specified {generator}).")


def build_targets_from_packages(project_config, package_names):
    if not package_names:
        return []

    available_src_dirs = source_directories(project_config)
    available_src_set = set(available_src_dirs)

    package_to_src = {
        package_name: src_dir
        for package_name, src_dir in project_config.get("srcs", {}).items()
        if src_dir in available_src_set
    }

    # Accept either a Spack package name or the checked-out repository name.
    known_packages = {**{src: src for src in available_src_dirs}, **package_to_src}

    missing_packages = []
    targets = []
    for package_name in package_names:
        if package_name not in known_packages:
            missing_packages.append(package_name)
            continue

        target = package_directory_target(project_config, known_packages[package_name])
        if target not in targets:
            targets.append(target)

    if missing_packages:
        msg = "The following packages are not checked out in the selected project:\n"
        for package_name in missing_packages:
            msg += f"\n - {package_name}"

        msg += "\n\nAvailable checked-out package repositories:\n"
        for package_name in available_src_dirs:
            msg += f"\n - {package_name}"

        tty.die(msg + "\n")

    return targets


def build(project_config, parallel, generator_options, targets=None):
    build_area = project_config["build"]
    generator_list = []
    if parallel:
        generator_list.append(f"-j{parallel}")
    if generator_options:
        generator_list += generator_options

    if generator_list:
        generator_list.insert(0, "--")

    all_arguments = ["cmake", "--build", build_area]
    if targets:
        all_arguments += ["--target"] + targets
    all_arguments += generator_list
    all_arguments_str = " ".join(all_arguments)
    print()
    tty.msg("Building with command:\n\n" + cyan(all_arguments_str) + "\n")

    subprocess.run(all_arguments)


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT, State.PACKAGES_TO_DEVELOP)

    config = selected_project_config()
    if args.clean:
        build_path = Path(config["build"])
        in_cwd = build_path.resolve() == Path.cwd().resolve()
        remove_dir(build_path, keep_dir=in_cwd)

    activate_development_environment(config["local"])

    build_area = config["build"]
    if not (Path(build_area) / "CMakeCache.txt").exists():
        configure(config, args.cmake_defines)

    if not args.configure_only:
        targets = build_targets_from_packages(config, args.packages)
        build(config, args.parallel, args.generator_options, targets)
