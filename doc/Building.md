# Building a project

Once you have selected an MPD project and activated its corresponding
environment, you may build your MPD project.  This is done by typing

```console
$ spack mpd build
```

The default build generator is `Make`, although the Ninja generator
can be specified with the `--generator` option:

```console
$ spack mpd build --generator Ninja
```

Generator commands may be specified after two contiguous hyphens `--`:

```console
$ spack mpd build --generator Ninja -- <generator commands> ...
```

It is also possible to *clean* the build area before running the build step:

```console
$ spack mpd build --clean ...
```

## Build commands

The `spack mpd build` command is just a wrapper for invoking two commands in the project's build directory:

```console
$ cmake --preset default <srcs dir> -B <build dir> -DCMAKE_INSTALL_PREFIX=<install dir>
$ cmake --build <build dir> -- <generator commands> ...
```

After the CMake configuration step has been completed (the first command above), you are permitted to use the generator commands directly if you are in the build directory of the project (e.g.):

```console
$ cmake --preset default <srcs dir> -B <build dir> -DCMAKE_INSTALL_PREFIX=<install dir>
$ ninja
```

This can be very helpful for doing iterative development where the CMake configuration command is not necessary.
