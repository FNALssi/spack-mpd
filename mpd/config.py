import os
from pathlib import Path

import ruamel
from ruamel.yaml.scalarstring import SingleQuotedScalarString as YamlQuote

import llnl.util.tty as tty

import spack.environment as ev
import spack.util.spack_yaml as syaml
from spack.parser import SPLIT_KVP, SpecParser, TokenType
from spack.repo import PATH
from spack.spec import Spec

from . import init
from .util import cyan, gray, magenta, spack_cmd_line

_DEFAULT_CXXSTD = "cxxstd=17"  # Must be a string for CMake
_DEFAULT_GENERATOR = "generator=make"
_NONE_STR = "(none)"


# Pilfered from https://stackoverflow.com/a/568285/3585575
def _process_exists(pid):
    """Check For the existence of a unix pid."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


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

    return {"top": _create_dir(top_path),
            "source": _create_dir(srcs_path),
            "build": _create_dir(top_path / "build"),
            "local": _create_dir(top_path / "local")}


def ordered_requirement_list(requirements):
    # Assemble things in the right order
    requirement_list = []
    for variant_name in ("version", "compiler"):
        if variant := requirements.pop(variant_name, None):
            requirement_list.append(YamlQuote(variant))

    # We don't care about the order of the remaining variants
    requirement_list += [YamlQuote(r) for r in requirements.values()]
    return requirement_list


def handle_variant(token):
    # Last specification wins (this behavior may need to be massaged)
    if token.kind in (TokenType.COMPILER, TokenType.COMPILER_AND_VERSION):
        compiler = token.value[1:]
        return compiler, token.value
    if token.kind in (TokenType.KEY_VALUE_PAIR, TokenType.PROPAGATED_KEY_VALUE_PAIR):
        match = SPLIT_KVP.match(token.value)
        name = match.group(1)
        return name, token.value
    if token.kind == TokenType.BOOL_VARIANT:
        name = token.value[1:].strip()
        return name, token.value
    if token.kind == TokenType.PROPAGATED_BOOL_VARIANT:
        name = token.value[2:].strip()
        return name, token.value
    elif token.kind == TokenType.VERSION:
        return "version", token.value

    tty.die(f"The variant '{token.value}' is not supported")


def handle_variants(project_cfg, variants):
    variant_str = " ".join(variants)
    tokens_from_str = SpecParser(variant_str).tokens()
    general_variant_map = {}
    package_variant_map = {}
    dependency_variant_map = {}
    compiler = None
    dependency = False
    variant_map = general_variant_map
    for token in tokens_from_str:
        if token.kind == TokenType.DEPENDENCY:
            dependency = True
            continue
        elif token.kind == TokenType.UNQUALIFIED_PACKAGE_NAME:
            parent_map = dependency_variant_map if dependency else package_variant_map
            variant_map = parent_map.setdefault(token.value, dict())
            continue

        name, variant = handle_variant(token)
        variant_map[name] = variant

    # Compiler
    if compiler:
        project_cfg["compiler"] = compiler
    elif "compiler" not in project_cfg:
        tty.warn("No compiler spec specified in the variants list " +
                 gray("(using environment default)"))
        project_cfg["compiler"] = None

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

    # Set packages
    srcs_path = Path(project_cfg["source"])
    assert srcs_path.exists()
    packages_to_develop = sorted(
        f.name for f in srcs_path.iterdir() if not f.name.startswith(".") and f.is_dir()
    )

    cxxstd = project_cfg["cxxstd"]
    generator = project_cfg["generator"]
    package_requirements = {}
    for p in packages_to_develop:
        # Check to see if packages support a 'cxxstd' variant
        spec = Spec(p)
        pkg_cls = PATH.get_pkg_class(spec.name)
        pkg = pkg_cls(spec)
        pkg_requirements = {}
        pkg_requirements["version"] = "@develop"
        if compiler := project_cfg["compiler"]:
            pkg_requirements["compiler"] = f"%{compiler}"
        maybe_has_variant = getattr(pkg, "has_variant", lambda _: False)
        if maybe_has_variant("cxxstd") or "cxxstd" in pkg.variants:
            pkg_requirements["cxxstd"] = cxxstd
        if maybe_has_variant("generator") or "generator" in pkg.variants:
            pkg_requirements["generator"] = generator

        # Go through remaining general variants
        for name, value in general_variant_map.items():
            if not maybe_has_variant(name) and name not in pkg.variants:
                continue

            pkg_requirements[name] = value

        pkg_requirements.update(package_variant_map.get(p, {}))

        package_requirements[spec.name] = dict(require=ordered_requirement_list(pkg_requirements))

    dependency_requirements = {}
    for name, requirements in dependency_variant_map.items():
        dependency_requirements[name] = dict(require=ordered_requirement_list(requirements))

    project_cfg["packages"] = package_requirements
    project_cfg["dependencies"] = dependency_requirements
    return project_cfg


def project_config_from_args(args):
    project = ruamel.yaml.comments.CommentedMap()
    project["name"] = args.name
    project["envs"] = args.env

    top_path = Path(args.top)
    srcs_path = Path(args.srcs) if args.srcs else top_path / "srcs"

    directories = prepare_project_directories(top_path, srcs_path)
    project.update(directories)
    return handle_variants(project, args.variants)


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


def update(project_config, status=None):
    config_file = mpd_config_file()
    config = None
    if config_file.exists():
        with open(config_file, "r") as f:
            config = syaml.load(f)

    if config is None:
        config = ruamel.yaml.comments.CommentedMap()
        config["projects"] = ruamel.yaml.comments.CommentedMap()

    yaml_project_config = ruamel.yaml.comments.CommentedMap()
    yaml_project_config.update(project_config)
    if status:
        yaml_project_config.update(status=status)
    config["projects"][project_config["name"]] = yaml_project_config

    # Update config file
    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)


def refresh(project_name, new_variants):
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
    config["projects"][project_name] = handle_variants(project_cfg, new_variants)

    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)

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
    with open(config_file, "w") as f:
        syaml.dump(config, stream=f)


def project_config(name, config=None):
    if config is None:
        config_file = mpd_config_file()
        if config_file.exists():
            with open(config_file, "r") as f:
                config = syaml.load(f)

    if config is None:
        print()
        tty.die("Missing MPD configuration.  Please contact scisoft-team@fnal.gov\n")

    projects = config.get("projects")
    if name not in projects:
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
        if not ev.is_env_dir(proj_config["local"]):
            proj_config["status"] = _NONE_STR
            adjusted = True
        deployed_env = proj_config.get("deployed", _NONE_STR)
        if deployed_env != _NONE_STR and not ev.exists(deployed_env):
            proj_config["deployed"] = _NONE_STR
            adjusted = True

    if adjusted:
        with open(mpd_config_file(), "w") as f:
            syaml.dump(config, stream=f)

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
    print(f"\nUsing {cyan('build')} area: {config['build']}")
    print(f"Using {cyan('local')} area: {config['local']}")
    print(f"Using {cyan('sources')} area: {config['source']}\n")
    packages = config["packages"]
    if not packages:
        return

    print("  Will develop:")
    for pkg, variants in packages.items():
        requirements = " ".join(variants["require"])
        print(f"    - {magenta(pkg)}{gray(requirements)}")


def select(name):
    session_id = os.getsid(os.getpid())
    selected = selected_projects_dir()
    selected.mkdir(exist_ok=True)
    (selected / f"{session_id}").write_text(name)
