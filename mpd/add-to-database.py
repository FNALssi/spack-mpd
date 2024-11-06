import sys
import traceback

import spack.environment as ev
import spack.store


def add_to_database(project_name: str, dag_hash: str):
    env = ev.read(project_name)
    try:
        spack.store.STORE.db.add(env.get_one_by_hash(dag_hash))
    except Exception:
        print(traceback.format_exc())


if __name__ == "__main__":
    assert len(sys.argv) == 3
    add_to_database(*sys.argv[1:])
