# Building a project

Once you have selected an MPD project and its development environment
has been installed, you may build your MPD project.  This is done by
typing

```console
$ spack mpd build
```

## Generator support

Each CMake package supported by Spack can be built with two
generators: either UNIX makefiles (`make`) or Ninja (`ninja`).  The
generator, however, is an ingredient to Spack's concretization
process, and it therefore must be specified as a variant during the
`spack mpd new-project` or `spack mpd refresh` commands.  For that
reason, the MPD build interface does not allow the specification of a
generator—the generator used during the concretization of the project
will be used during the build.

The build command supports a parallelism argument (`-j<ncores>`), an
option to pass CMake variable definitions (`-D<var>:<type>=<value>`),
and the command also allows the specification of generator commands
after the double hyphen (`--`):

```console
$ spack mpd build -j12 -D<var>:<type>=<value> -- <generator commands> ...
```

It is also possible to *clean* the build area before running the build step:

```console
$ spack mpd build --clean ...
```

## Build commands

The `spack mpd build` command is just a wrapper for invoking two
commands in the project's build directory _with an activated
development environment_:

```console
$ spack env activate <mpd project local directory>
$ cmake --preset default <srcs dir> -B <build dir> -G <generator>
$ cmake --build <build dir> -- <generator commands> ...
$ spack env deactivate
```

After the CMake configuration step has been completed (the first
command above), you may use the generator commands directly if you are
in the build directory of the project (e.g.):

```console
$ spack env activate <mpd project local directory>
$ cd <build dir>
$ cmake --preset default <srcs dir> ...
$ ninja
$ spack env deactivate
```

This can be very helpful for doing iterative development where the
CMake configuration command is not necessary.  The `spack mpd build`
command, however, takes steps to avoid needless CMake reconfiguration.

> [!NOTE]
> You do not need to explicitly activate the development environment
> to invoke `spack mpd build`.  Activating it is only necessary if
> you'd like to invoke either the `cmake` or generator commands
> directly in the build directory of the MPD project.
