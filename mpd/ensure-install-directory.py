import sys

import spack.environment as ev
import spack.store


def ensure_install_directory(dag_hash: str):
    env = ev.active_environment()
    spack.store.STORE.layout.create_install_directory(env.get_one_by_hash(dag_hash))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    ensure_install_directory(sys.argv[1])
