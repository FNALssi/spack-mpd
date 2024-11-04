import sys

import spack.environment as ev
import spack.store


def add_to_database(dag_hash: str):
    env = ev.active_environment()
    spack.store.STORE.db.add(env.get_one_by_hash(dag_hash))


if __name__ == "__main__":
    assert len(sys.argv) == 2
    add_to_database(sys.argv[1])
