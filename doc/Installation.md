# Installing MPD

   Note: if you installed Spack with the `bootstrap` script from `fermi-spack-tools`, this will already have been done for you.

1. Clone the [`spack-mpd` repository](https://github.com/knoepfel/spack-mpd).
2. Invoke `spack config edit config` and add the following to your configuration:
    ```yaml
    config:
      extensions:
      - <path to your local spack-mpd clone>
    ```
3. (Optional) You may find it beneficial to specify an alias in your `.bashrc` file to avoid typing `spack mpd` (e.g.):
    ```console
    alias mpd="spack mpd"
    ```

## Check your installation

At this point you, should be able to invoke `spack help --all` and see:

```console
$ spack help --all
⋮
developer:
  ⋮
  mpd                   develop multiple packages using Spack for external software
⋮
```

and furthermore, if you type `spack mpd --help` you should see something like:

```console
$ spack mpd -h
usage: spack mpd [-hV] SUBCOMMAND ...

develop multiple packages using Spack for external software

positional arguments:
  SUBCOMMAND
    build (b)           build repositories
    clear               clear selected MPD project
    git-clone (g, clone)
                        clone git repositories
    init                initialize MPD on this system
    install (i)         install built repositories
    list (ls)           list MPD projects
    new-project (n)     create MPD development area
    refresh             refresh project
    rm-project (rm)     remove MPD project
    select              select MPD project
    status              current MPD status
    test (t)            build and run tests
    zap (z)             delete everything in your build and/or install areas

optional arguments:
  -V, --version         print MPD version (0.2.0) and exit
  -h, --help            show this help message and exit
```

Now that MPD has been installed, you can [initialize your system to use MPD](Initialization.md).

### Running MPD's unit tests

MPD has several unit tests that should run successfully for any system on which it is installed.  If you wish to run the unit tests, invoke:

```console
$ spack unit-test --extension mpd
========================================= test session starts ==========================================
platform linux -- Python 3.9.18, pytest-8.2.1, pluggy-1.5.0
rootdir: /home/knoepfel/spack-mpd
configfile: pytest.ini
testpaths: tests
collected 7 items

tests/test_mpd_clone.py .                                                                        [ 14%]
tests/test_mpd_init.py .                                                                         [ 28%]
tests/test_mpd_new_project.py .....                                                              [100%]

========================================= slowest 30 durations =========================================
1.48s call     tests/test_mpd_clone.py::test_new_project_clone
1.15s call     tests/test_mpd_new_project.py::test_mpd_refresh
1.12s call     tests/test_mpd_new_project.py::test_new_project_all_default_paths
1.12s call     tests/test_mpd_new_project.py::test_new_project_only_top_path
1.05s call     tests/test_mpd_new_project.py::test_new_project_no_default_paths
1.05s call     tests/test_mpd_new_project.py::test_new_project_only_srcs_path
0.08s call     tests/test_mpd_init.py::test_mpd_init
0.04s setup    tests/test_mpd_clone.py::test_new_project_clone
0.04s setup    tests/test_mpd_new_project.py::test_new_project_all_default_paths
0.04s setup    tests/test_mpd_new_project.py::test_new_project_only_srcs_path
0.03s setup    tests/test_mpd_new_project.py::test_new_project_no_default_paths
0.03s setup    tests/test_mpd_new_project.py::test_new_project_only_top_path
0.03s setup    tests/test_mpd_new_project.py::test_mpd_refresh

(8 durations < 0.005s hidden.  Use -vv to show these durations.)
========================================== 7 passed in 7.30s ===========================================
```

If you encounter any failures, please [report an issue](https://github.com/knoepfel/spack-mpd/issues).
