# Installing MPD

To install MPD:

1. Clone the [`spack-mpd` repository](https://github.com/knoepfel/spack-mpd).
2. Invoke `spack config edit config` and add the following to your configuration:
    ```yaml
    config:
      extensions:
      - <path to your local spack-mpd clone>
    ```

At this point you, should be able to invoke `spack help --all` and see:

```console
$ spack help --all
...
scripting:
  mpd                   develop multiple packages using Spack for external software
...
```

Now that MPD has been installed, you can [initialize your system to use MPD](doc/Initialization.md).
