import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

import spack.compilers.config

try:
    from spack.vendor.ruamel.yaml import comments
except ImportError:
    from ruamel.yaml import comments

try:
    from spack.vendor.ruamel.yaml.scalarstring import SingleQuotedScalarString as YamlQuote
except ImportError:
    from ruamel.yaml.scalarstring import SingleQuotedScalarString as YamlQuote

import spack.compilers
import spack.config
import spack.environment as ev
import spack.llnl.util.tty as tty
import spack.store
import spack.util.spack_yaml as syaml
from spack.repo import PATH, UnknownPackageError
from spack.spec import Spec
from spack.spec_parser import SPLIT_KVP, SpecParser, SpecTokens

try:
    from spack.build_systems.cmake import CMakePackage
except ImportError:
    PATH.repos
    from spack_repo.builtin.build_systems.cmake import CMakePackage

from . import init
from .util import cyan, gray, green, magenta, spack_cmd_line, yellow


def _variant_pair(value, variant):
    return dict(value=value, variant=variant)


UNINSTALLED = "---"

_DEFAULT_CXXSTD = _variant_pair(value="17", variant="cxxstd=17")
_DEFAULT_GENERATOR = _variant_pair(value="make", variant="generator=make")
_DEVELOP_VARIANT = _variant_pair(value="develop", variant="@develop")


# Pilfered from https://stackoverflow.com/a/568285/3585575
def _process_exists(pid):
    """Check For the existence of a unix pid."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _depends_on_ccxx(pkg):
    return "c" in pkg.dependency_names() or "cxx" in pkg.dependency_names()


def mpd_config_dir():
    return init.mpd_config_dir()


def mpd_config_file():
    return init.mpd_config_file(mpd_config_dir())


def selected_projects_dir():
    return init.mpd_selected_projects_dir(mpd_config_dir())


def selected_projects():
    projects = {}
    for sp in selected_projects_dir().iterdir():
        project_name = sp.read_text()
        projects.setdefault(project_name, []).append(sp.name)
    return projects


def session_id():
    return f"{os.getsid(os.getpid())}"


def selected_project_token():
    projects_dir = selected_projects_dir()
    return projects_dir / session_id() if projects_dir else None


def mpd_config():
    config_file = mpd_config_file()
    if not config_file.exists():
        return None

    with open(config_file, "r") as f:
        return syaml.load(f)
    return None


def prepare_project_directories(top_path, srcs_path):
    def _create_dir(path):
        path.mkdir(exist_ok=True)
        return str(path.absolute())

    return {
        "top": _create_dir(top_path),
        "source": _create_dir(srcs_path),
        "build": _create_dir(top_path / "build"),
        "local": _create_dir(top_path / "local"),
    }


def ordered_requirement_list(requirements):
    # Assemble things in the right order
    requirement_list = []

    version = requirements.pop("version", None)
    compiler = requirements.pop("compiler", None)

    # Version goes first
    if version:
        requirement_list.append(version)

    # We don't care about the order of the remaining variants...
    requirement_list += [r for r in requirements.values()]

    # ... except the compiler must go last
    if compiler:
        requirement_list.append(YamlQuote(compiler))

    return requirement_list


def all_available_compilers():
    # Pilfered from https://github.com/spack/spack/blob/182c615df98bda5d3c1e26513e3a52c40b4efbec/lib/spack/spack/cmd/compiler.py#L222
    supported_compilers = spack.compilers.config.supported_compilers()

    def _is_compiler(x):
        return x.name in supported_compilers and x.package.supported_languages and not x.external

    compilers_from_store = [x for x in spack.store.STORE.db.query() if _is_compiler(x)]
    compilers_from_yaml = spack.compilers.config.all_compilers(scope=None, init_config=False)
    return compilers_from_yaml + compilers_from_store


def handle_variant(token):
    if token.kind in (SpecTokens.KEY_VALUE_PAIR, SpecTokens.PROPAGATED_KEY_VALUE_PAIR):
        match = SPLIT_KVP.match(token.value)
        name, _, value = match.groups()
        return name, _variant_pair(value, token.value)
    if token.kind == SpecTokens.BOOL_VARIANT:
        name = token.value[1:].strip()
        return name, _variant_pair(token.value[0] == "+", token.value)
    if token.kind == SpecTokens.PROPAGATED_BOOL_VARIANT:
        name = token.value[2:].strip()
        return name, _variant_pair(token.value[:2] == "++", token.value)
    elif token.kind == SpecTokens.VERSION:
        return "version", _variant_pair(token.value[1:], token.value)

    tty.die(f"The token '{token.value}' is not supported")


def spack_packages(srcs_dir):
    srcs_path = Path(srcs_dir)
    assert srcs_path.exists()
    srcs_repos = sorted(
        f.name for f in srcs_path.iterdir() if not f.name.startswith(".") and f.is_dir()
    )

    # Check for unknown packages
    unknown_packages = []
    packages_to_develop = {}
    for p in srcs_repos:
        spec = Spec(p)
        try:
            pkg_cls = PATH.get_pkg_class(spec.name)
            packages_to_develop[p] = pkg_cls(spec)
        except UnknownPackageError:
            unknown_packages.append(p)

    if unknown_packages:
        print()
        msg = "The following directories do not correspond to any known Spack package:\n"
        for p in unknown_packages:
            msg += f"\n - {srcs_path / p}"
        tty.die(msg + "\n")

    return packages_to_develop


def parse_dependency_spec(dependency_spec):
    """
    Parse a dependency specification like 'root%gcc@11' or 'foo ^bar@x.y.z'.
    Returns (package_name, list_of_constraint_strings).
    """
    tokens = list(SpecParser(dependency_spec).tokens())
    if not tokens:
        return None, []

    # First token should be the package name
    if tokens[0].kind != SpecTokens.UNQUALIFIED_PACKAGE_NAME:
        tty.die(f"Dependency spec must start with a package name: '{dependency_spec}'")

    package_name = tokens[0].value
    constraints = []

    # Process remaining tokens to build constraint strings
    i = 1
    while i < len(tokens):
        token = tokens[i]

        if token.kind == SpecTokens.DEPENDENCY:
            # Next token should be a package name for the dependency
            if i + 1 >= len(tokens):
                tty.die(f"Incomplete dependency specification in '{dependency_spec}'")

            # Build dependency constraint: ^package + any following constraints
            dep_constraint = "^" + tokens[i + 1].value
            i += 2

            # Collect any version/variant info for this dependency
            while i < len(tokens) and tokens[i].kind != SpecTokens.DEPENDENCY:
                if tokens[i].kind == SpecTokens.UNQUALIFIED_PACKAGE_NAME:
                    # Another package name without ^ means something is wrong
                    break
                dep_constraint += tokens[i].value
                i += 1

            constraints.append(dep_constraint)
        else:
            # Regular constraint (version, variant, compiler, etc.)
            if token.kind == SpecTokens.UNQUALIFIED_PACKAGE_NAME:
                tty.die(
                    f"Unexpected package name '{token.value}' in dependency "
                    f"spec '{dependency_spec}'. Did you mean to use '^' before it?"
                )
            constraints.append(token.value)
            i += 1

    return package_name, constraints


def categorize_constraints(constraints):
    """
    Categorize constraint strings into a map for ordered_requirement_list.
    Takes constraint strings like '%gcc@11', '^bar@x.y.z', '@1.2.3', 'cxxstd=20', etc.
    Returns a dictionary mapping constraint names to variant pairs.
    """
    constraint_map = {}
    for constraint_str in constraints:
        # Categorize the constraint based on its first character
        if constraint_str.startswith("^"):
            # Dependency constraint: extract dependency name as key
            # e.g., "^bar@x.y.z" -> key="bar", value="^bar@x.y.z"
            dep_name = (
                constraint_str.split("@")[0].split("%")[0].split("+")[0].split("~")[0][1:]
            )  # Remove ^
            constraint_map[dep_name] = _variant_pair(dep_name, constraint_str)
        elif constraint_str.startswith("%"):
            # Compiler constraint
            constraint_map["compiler"] = _variant_pair(constraint_str[1:], constraint_str)
        elif constraint_str.startswith("@"):
            # Version constraint
            constraint_map["version"] = _variant_pair(constraint_str[1:], constraint_str)
        else:
            # Other constraints (variants, etc.)
            # Try to extract a name from the constraint
            if "=" in constraint_str:
                name = constraint_str.split("=")[0]
            elif constraint_str.startswith("+") or constraint_str.startswith("~"):
                name = constraint_str[1:]
            else:
                name = constraint_str
            constraint_map[name] = _variant_pair(name, constraint_str)

    return constraint_map


def parse_general_variants(variants):
    """
    Parse general variants (positional args) and categorize them.
    Returns tuple: (general_variant_map, package_variant_map, virtual_dependencies)

    - general_variant_map: variants that apply to all packages (e.g., cxxstd=20)
    - package_variant_map: package-specific variants (e.g., root +variant)
    - virtual_dependencies: virtual package providers (e.g., [virtuals=mpi])
    """
    variant_str = " ".join(variants)
    tokens_from_str = SpecParser(variant_str).tokens()
    general_variant_map = {}
    package_variant_map = {}
    virtual_package = None
    virtual_dependency = False
    virtual_dependencies = {}
    concrete_package_expected = False
    variant_map = general_variant_map

    for token in tokens_from_str:
        if token.kind == SpecTokens.DEPENDENCY:
            # ^ character found in variants - this is no longer supported for creating dependencies
            tty.die(
                "Using '^' in variants to specify dependencies is no longer supported.\\n"
                "Please use the --dependency flag instead, e.g.:\\n"
                "  spack mpd refresh --dependency 'package ^dep@version'\\n"
                "  spack mpd new-project --dependency 'package ^dep@version'"
            )
        if token.kind == SpecTokens.START_EDGE_PROPERTIES:
            virtual_dependency = True
            continue
        if token.kind == SpecTokens.END_EDGE_PROPERTIES:
            virtual_dependency = False
            concrete_package_expected = True
            continue
        if token.kind == SpecTokens.UNQUALIFIED_PACKAGE_NAME:
            if concrete_package_expected:
                virtual_dependencies.setdefault(virtual_package, []).append(token.value)
                virtual_package = None
                concrete_package_expected = False
            else:
                # Package name in variants - this is for package-specific variants
                variant_map = package_variant_map.setdefault(token.value, dict())
            continue

        name, variant_pair = handle_variant(token)
        if virtual_dependency:
            virtual_package = variant_pair["value"]
        else:
            variant_map[name] = variant_pair

    return general_variant_map, package_variant_map, virtual_dependencies


def apply_project_defaults(project_cfg, general_variant_map, variants):
    """Extract and apply project-level defaults from general variant map."""
    # CXX standard
    if "cxxstd" in general_variant_map:
        cxxstd_variant = general_variant_map.pop("cxxstd")
        project_cfg["cxxstd"] = cxxstd_variant
    elif "cxxstd" not in project_cfg:
        project_cfg["cxxstd"] = _DEFAULT_CXXSTD

    # Generator
    if "generator" in general_variant_map:
        generator_variant = general_variant_map.pop("generator")
        project_cfg["generator"] = generator_variant
    elif "generator" not in project_cfg:
        project_cfg["generator"] = _DEFAULT_GENERATOR

    if variants:
        project_cfg["variants"] = " ".join(variants)


def validate_package_variants(package_variant_map, packages_to_develop):
    """Ensure that packages in package_variant_map are actually cloned."""
    not_cloned = []
    for k, v in package_variant_map.items():
        if k not in packages_to_develop:
            not_cloned.append((k, v))

    if not_cloned:
        err_msg = "The following specifications correspond to packages that are not "
        err_msg += "under development:\n"
        for k, variants in not_cloned:
            only_variants = {key: value["variant"] for key, value in variants.items()}
            requirements = " ".join(ordered_requirement_list(only_variants))
            # Only the '@' sign can be directly next to the package name
            if requirements and requirements[0] != "@":
                requirements = " " + requirements
            err_msg += f"\n - {k}{requirements}"
        err_msg += "\n\nThe packages should either be cloned, or if they are intended to be\n"
        err_msg += (
            "constraints on dependencies, they should be specified with the --dependency flag."
        )
        tty.die(err_msg)


def build_package_requirements(
    pkg_name, pkg, packages, cxxstd, generator, compiler, general_variant_map, package_variant_map
):
    """Build requirements for a single package."""
    # Start with existing requirements
    existing_pkg_requirements = packages.get(pkg_name, {}).get("require", [])
    existing_pkg_requirements_str = " ".join(existing_pkg_requirements)
    pkg_requirements = {}
    dependency = False  # Track dependency context when parsing existing requirements
    for token in SpecParser(existing_pkg_requirements_str).tokens():
        if token.kind == SpecTokens.DEPENDENCY:
            dependency = True
            continue
        if dependency and token.kind == SpecTokens.UNQUALIFIED_PACKAGE_NAME:
            dependency = False
            continue

        name, variant = handle_variant(token)
        pkg_requirements[name] = variant["variant"]

    # Check to see if packages support a 'cxxstd' variant
    pkg_requirements["version"] = _DEVELOP_VARIANT["variant"]
    maybe_has_variant = getattr(pkg, "has_variant", lambda _: False)
    if _depends_on_ccxx(pkg) and compiler:
        pkg_requirements["compiler"] = compiler["variant"]
        if maybe_has_variant("cxxstd") or "cxxstd" in pkg.variants:
            pkg_requirements["cxxstd"] = cxxstd["variant"]
    if maybe_has_variant("generator") or "generator" in pkg.variants:
        pkg_requirements["generator"] = generator["variant"]

    # Go through remaining general variants
    for name, value in general_variant_map.items():
        if not maybe_has_variant(name) and name not in pkg.variants:
            continue

        pkg_requirements[name] = value["variant"]

    only_variants = {k: v["variant"] for k, v in package_variant_map.get(pkg_name, {}).items()}
    pkg_requirements.update(only_variants)

    return dict(require=ordered_requirement_list(pkg_requirements))


def build_all_package_requirements(
    packages_to_develop, project_cfg, general_variant_map, package_variant_map
):
    """Build package requirements for all packages to develop."""
    packages = project_cfg.get("packages", {})
    # We need to make sure that the packages cached in the configuration file still exist
    packages = {key: value for key, value in packages.items() if key in packages_to_develop}

    cxxstd = project_cfg["cxxstd"]
    generator = project_cfg["generator"]
    compiler = project_cfg.get("compiler")

    ignored_packages = []
    languages = set()

    for pkg_name, pkg in packages_to_develop.items():
        if not issubclass(type(pkg), CMakePackage):
            ignored_packages.append(pkg_name)
            continue

        # Check languages
        for dependency in pkg.dependencies.values():
            # Each 'dependency' corresponds to a depends_on(...) directive
            if "c" in dependency:
                languages.add("c")
            if "cxx" in dependency:
                languages.add("cxx")
            if "python" in dependency:
                languages.add("python")

        packages[pkg_name] = build_package_requirements(
            pkg_name,
            pkg,
            packages,
            cxxstd,
            generator,
            compiler,
            general_variant_map,
            package_variant_map,
        )

    return packages, ignored_packages, languages


def build_dependency_requirements(dependency_variant_map, virtual_dependencies, project_cfg):
    """Build dependency requirements from dependency_variant_map and virtual_dependencies."""
    dependency_requirements = project_cfg.get("dependencies", {})
    for name, requirements in dependency_variant_map.items():
        only_variants = {key: value["variant"] for key, value in requirements.items()}
        dependency_requirements[name] = dict(require=ordered_requirement_list(only_variants))

    # Handle virtual dependencies
    if virtual_dependencies:
        dependency_requirements["all"] = dict(providers=virtual_dependencies)

    return dependency_requirements


def handle_variants(project_cfg, variants, dependencies=None):
    """
    Process variants and dependencies, updating project configuration.

    Args:
        project_cfg: Project configuration dictionary
        variants: List of general variant strings (positional args)
        dependencies: List of dependency spec strings (from --dependency flag)

    Returns:
        Updated project_cfg dictionary
    """
    # Process explicit dependencies (new --dependency flag)
    dependency_variant_map = {}
    if dependencies:
        for dep_spec in dependencies:
            pkg_name, constraints = parse_dependency_spec(dep_spec)
            if not pkg_name:
                continue
            dependency_variant_map[pkg_name] = categorize_constraints(constraints)

    # Parse general variants (positional args)
    general_variant_map, package_variant_map, virtual_dependencies = parse_general_variants(
        variants
    )

    # Apply project-level defaults (cxxstd, generator)
    apply_project_defaults(project_cfg, general_variant_map, variants)

    # Get packages to develop and validate package_variant_map
    packages_to_develop = spack_packages(project_cfg["source"])
    validate_package_variants(package_variant_map, packages_to_develop)

    # Build package requirements
    packages, ignored_packages, languages = build_all_package_requirements(
        packages_to_develop, project_cfg, general_variant_map, package_variant_map
    )

    # Build dependency requirements
    dependency_requirements = build_dependency_requirements(
        dependency_variant_map, virtual_dependencies, project_cfg
    )

    # Update project configuration
    project_cfg["packages"] = packages
    project_cfg["ignored"] = ignored_packages
    project_cfg["dependencies"] = dependency_requirements
    project_cfg["languages"] = list(languages)

    return project_cfg


def select_compiler(desired_compiler):
    """Select and validate compiler based on project configuration.

    Args:
        desired_compiler: Compiler specification dictionary (or None) from project config

    Returns:
        The chosen compiler spec
    """
    compilers = []
    all_compilers = all_available_compilers()
    if desired_compiler:
        desired_compiler_value = desired_compiler["value"]
        compilers = [c for c in all_compilers if c.satisfies(desired_compiler_value)]

        if not compilers:
            desired_compiler_variant = desired_compiler["variant"]
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

    chosen_compiler = compilers[0]
    return chosen_compiler


def project_config_from_args(args):
    project = comments.CommentedMap()
    top_path = Path(args.top)
    project["name"] = args.name if args.name else top_path.name
    project["env"] = args.env

    srcs_path = Path(args.srcs) if args.srcs else top_path / "srcs"

    directories = prepare_project_directories(top_path, srcs_path)
    project.update(directories)

    # Handle explicit --compiler argument
    compiler_arg = getattr(args, "compiler", None)
    if compiler_arg:
        project["compiler"] = _variant_pair(compiler_arg, "%" + compiler_arg)
    else:
        tty.warn(
            "No compiler spec specified "
            + gray(
                "(will attempt to use default; project creation will fail if none is available)"
            )
        )

    # Select and validate compiler
    chosen_compiler = select_compiler(project.get("compiler"))

    # The compiler paths are selected differently depending on whether the compiler is an
    # external package or an installed one.
    compiler_paths = {}
    if chosen_compiler.external:
        compiler_paths = chosen_compiler.extra_attributes["compilers"]
    else:
        if cc := getattr(chosen_compiler.package, "cc", None):
            compiler_paths["c"] = cc
        if cxx := getattr(chosen_compiler.package, "cxx", None):
            compiler_paths["cxx"] = cxx

    project["chosen_compiler"] = str(chosen_compiler)
    project["compiler_paths"] = compiler_paths

    # Join dependency token lists into strings
    dependencies = getattr(args, "dependencies", None)
    if dependencies:
        dependencies = [" ".join(dep_tokens) for dep_tokens in dependencies]
    return handle_variants(project, args.variants, dependencies)


def mpd_project_exists(project_name):
    config_file = mpd_config_file()
    config = None
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    if config is None:
        return False

    projects = config.get("projects")
    if projects is None:
        return False

    return project_name in projects


def update(project_config, status=None, installed_at=None):
    config_file = mpd_config_file()
    config = None
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    if config is None:
        config = comments.CommentedMap()
        config["projects"] = comments.CommentedMap()

    yaml_project_config = comments.CommentedMap()
    yaml_project_config.update(project_config)
    if status:
        yaml_project_config.update(status=status)
    if installed_at:
        yaml_project_config.update(installed=installed_at)
    config["projects"][project_config["name"]] = yaml_project_config

    # Update config file
    with NamedTemporaryFile() as f:
        syaml.dump(config, stream=f)
        shutil.copy(f.name, config_file)


def refresh(project_name, new_variants, new_dependencies=None):
    config_file = mpd_config_file()
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    # Update packages field
    assert config is not None
    assert project_name is not None
    project_cfg = project_config(project_name, config)

    top_path = Path(project_cfg["top"])
    srcs_path = Path(project_cfg["source"])

    prepare_project_directories(top_path, srcs_path)
    config["projects"][project_name] = handle_variants(project_cfg, new_variants, new_dependencies)
    with NamedTemporaryFile() as f:
        syaml.dump(config, stream=f)
        shutil.copy(f.name, config_file)

    # Return configuration for this project
    return config["projects"][project_name]


def rm_config(project_name):
    config_file = mpd_config_file()
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    assert config is not None
    assert project_name is not None

    # Remove project entry
    del config["projects"][project_name]
    with NamedTemporaryFile() as f:
        syaml.dump(config, stream=f)
        shutil.copy(f.name, config_file)


def project_config(name, config=None, missing_ok=False):
    if config is None:
        config_file = mpd_config_file()
        if config_file.exists():
            with open(config_file, "r") as f:
                config = syaml.load(f)

    if config is None:
        if missing_ok:
            return None
        print()
        tty.die("Missing MPD configuration.  Please contact scisoft-team@fnal.gov\n")

    projects = config.get("projects")
    if name not in projects:
        if missing_ok:
            return None
        print()
        tty.die(
            f"Project '{name}' not supported by MPD configuration."
            " Please contact scisoft-team@fnal.gov\n"
        )

    return projects[name]


def update_cache():
    # Update environment status in user configuration
    config = mpd_config()
    if not config:
        return

    projects = config.get("projects")
    if not projects:
        return

    adjusted = False
    for name, proj_config in projects.items():
        if "status" in proj_config and not ev.is_env_dir(proj_config["local"]):
            del proj_config["status"]
            adjusted = True
        if "installed" in proj_config and not ev.exists(name):
            del proj_config["installed"]
            adjusted = True

    if adjusted:
        with NamedTemporaryFile() as f:
            syaml.dump(config, stream=f)
            shutil.copy(f.name, mpd_config_file())

    # Remove stale selected project tokens
    for sp in selected_projects_dir().iterdir():
        if not _process_exists(int(sp.name)):
            sp.unlink()
            continue
        selected_prj = sp.read_text()
        if selected_prj not in projects:
            sp.unlink()

    # Implicitly select project if environment is active
    active_env = ev.active_environment()
    if not active_env:
        return

    for name, config in projects.items():
        if active_env.path in config["local"]:
            selected_project_token().write_text(name)


def selected_project(missing_ok=True):
    token = selected_project_token()
    if token and token.exists():
        return token.read_text()

    if missing_ok:
        return None

    print()
    tty.die(f"Active MPD project required to invoke '{spack_cmd_line()}'\n")


def selected_project_config():
    return project_config(selected_project())


def print_config_info(config):
    print("\n  Project directories:")
    print(f"    {cyan('top')}     {config['top']}")
    print(f"    {cyan('build')}   {config['build']}")
    print(f"    {cyan('local')}   {config['local']}")
    print(f"    {cyan('sources')} {config['source']}\n")
    packages = config["packages"]
    if not packages:
        return

    ignored_packages = config["ignored"]
    all_packages = {}
    for ip in ignored_packages:
        all_packages[ip] = f"*{gray(ip)}"

    for pkg, variants in packages.items():
        requirements = " ".join(variants["require"])
        all_packages[pkg] = f" {magenta(pkg)}{gray(requirements)}"

    print("  Packages to develop:")
    for _, msg_for_pkg in sorted(all_packages.items()):
        print(f"   {msg_for_pkg}")

    if len(ignored_packages):
        print("\n    *" + gray("ignored: repository not registered as a CMake package with Spack"))

    if env := config["env"]:
        print(f"\n  Reusing dependencies from environment:\n    {green(env)}")

    dependencies = config["dependencies"]
    if not dependencies:
        return

    print("\n  Subject to the constraints:")
    for pkg, variants in dependencies.items():
        # Handle virtual dependencies
        if pkg == "all":
            for virtual, concretes in variants["providers"].items():
                for c in concretes:
                    line = f"^[virtuals={virtual}] {c}"
                    print(f"    {yellow(line)}")
            continue
        requirements = " ".join(variants["require"])
        # Only the '@' sign can be directly next to the package name
        if requirements and requirements[0] != "@":
            requirements = " " + requirements
        print(f"    {yellow(pkg)}{gray(requirements)}")


def select(name):
    session_id = os.getsid(os.getpid())
    selected = selected_projects_dir()
    selected.mkdir(exist_ok=True)
    (selected / f"{session_id}").write_text(name)
