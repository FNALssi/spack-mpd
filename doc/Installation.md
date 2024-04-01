# Installing MPD

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
...
scripting:
  mpd                   develop multiple packages using Spack for external software
...
```

and furthermore, if you type `spack mpd --help` you should see something like:

```console
$ spack mpd --help
usage: spack mpd [-hV] SUBCOMMAND ...

develop multiple packages using Spack for external software

positional arguments:
  SUBCOMMAND
    build (b)           build repositories
    clear               clear selected MPD project
    git-clone (g, gitCheckout)
                        clone git repositories
    init                initialize MPD on this system
    install (i)         install built repositories
    list (ls)           list MPD projects
    new-project (n, newDev)
                        create MPD development area
    refresh             refresh project area
    rm-project (rm)     remove MPD project
    select              select MPD project
    test (t)            build and run tests
    zap (z)             delete everything in your build and/or install areas

optional arguments:
  -V, --version         print MPD version (0.1.0) and exit
  -h, --help            show this help message and exit
```

Now that MPD has been installed, you can [initialize your system to use MPD](Initialization.md).
