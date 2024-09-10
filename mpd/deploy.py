import os
import subprocess
from pathlib import Path

import llnl.util.tty as tty

import spack.environment as ev
from spack.repo import PATH
from spack.spec import Spec

from .config import mpd_config_dir, selected_project_config, update
from .preconditions import State, preconditions
from .util import bold, make_yaml_file

SUBCOMMAND = "deploy"
ALIASES = ["d"]


def setup_subparser(subparsers):
    default_cpu = os.cpu_count() // 2
    deploy = subparsers.add_parser(
        SUBCOMMAND,
        description="deploy developed packages as installed Spack packages",
        aliases=ALIASES,
        help="deploy developed packages",
    )
    deploy.add_argument("name", help="name of deployed environment")
    deploy.add_argument(
        "-f", "--force", action="store_true", help="overwrite existing deployment environment"
    )
    deploy.add_argument(
        "-j",
        dest="parallel",
        metavar="<number>",
        default=default_cpu,
        help=f"specify number of threads for parallel build (default: {default_cpu})",
    )


def deploy(config, deployed_name, parallel, force):
    name = config["name"]
    source_path = Path(config["source"])
    assert source_path.exists()
    packages = config["packages"]
    developed_packages = {}
    for p in packages:
        # Check to see if packages support a 'cxxstd' variant
        spec = Spec(p)
        pkg_cls = PATH.get_pkg_class(spec.name)
        pkg = pkg_cls(spec)
        base_spec = f"{p}@develop %{config['compiler']}"
        if "cxxstd" in pkg.variants:
            base_spec += f" cxxstd={config['cxxstd']}"

        developed_packages[p] = dict(spec=base_spec, path=str(source_path / p))

    full_block = dict(
        include_concrete=[ev.root(name)],
        specs=[config["compiler"]] + packages,
        definitions=[dict(compiler=[config["compiler"]])],
        concretizer=dict(unify=True, reuse=True),
        develop=developed_packages,
    )
    env_file = make_yaml_file(deployed_name, dict(spack=full_block), prefix=mpd_config_dir())

    if ev.exists(deployed_name) and force:
        ev.read(deployed_name).destroy()

    env = ev.create(deployed_name, init_file=env_file)
    tty.info(f"Deployment environment {deployed_name} has been created")

    with env, env.write_transaction():
        env.concretize()
        env.write()

    result = subprocess.run(["spack", "-e", deployed_name, "install", f"-j{parallel}"])
    if result.returncode == 0:
        print()
        update(config, deployed_env=deployed_name)
        tty.msg(f"MPD project {name} has been deployed as {bold(deployed_name)}.\n")


def process(args):
    preconditions(State.INITIALIZED, State.SELECTED_PROJECT)

    config = selected_project_config()
    deploy(config, args.name, args.parallel, args.force)
