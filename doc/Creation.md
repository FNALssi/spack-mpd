# Creating an MPD project

An MPD project consists of:

- A name to distinguish it from other MPD projects.

- A top-level directory, which will contain (at a minimum) two
  subdirectories created by MPD: `build` and `local`.

- A sources directory, which contains CMake-based
  repositories (or symbolic links to repositories) to be developed.

There are two different ways to create an MPD project:

1. From an existing set of repositories that you would like to develop
2. From an empty set of repositories that you wish MPD to populate by `git`-cloning repositories

Both approaches are supported through the `spack mpd new-project` command:

```console
$ spack mpd new-project --help
usage: spack mpd new-project [-hCdfy] [--name NAME] [-T TOP] [-S SRCS] [-E ENV]
                             [-C COMPILER] [-d SPEC [CONSTRAINT ...]] [variants ...]

create MPD development area

positional arguments:
  variants              variants to apply to developed packages

optional arguments:
  --name NAME           (required if --top not specified)
  -C COMPILER, --compiler COMPILER
                        compiler to use (e.g., gcc@13.2.0, clang@15.0.0)
  -E ENV, --env ENV     environment from which to create project
                        (multiple allowed)
  -S SRCS, --srcs SRCS  directory containing repositories to develop
                        (default: <top-level directory>/srcs)
  -T TOP, --top TOP     top-level directory for MPD area
                        (default: /scratch/knoepfel/art-devel)
  -d SPEC [CONSTRAINT ...], --dependency SPEC [CONSTRAINT ...]
                        specify a package with constraints (e.g., root %gcc@11, foo ^bar@x.y.z)
                        (can be specified multiple times)
  -f, --force           overwrite existing project with same name
  -h, --help            show this help message and exit
  -y, --yes-to-all      Answer yes/default to all prompts
```

A few observations:

- `--name` is required unless `--top` is specified, in which case the
  project name defaults to the name of the top-level directory.  All
  other program options have defaults provided by MPD.

- The default top-level directory of your MPD project is the current
  working directory (the one in which you invoke `spack mpd
  new-project`).  Unless specified otherwise, the sources directory
  will be a subdirectory of the top-level directory.

## Variant support

Two categories of positional variants can be specified:

1. _general variants_, which are not prefaced with a package name, but
   are applied to any developed package that supports them
   (e.g. `cxxstd=20`, `generator=ninja`)
2. _developed-package variants_, which apply to a specific developed
   package and are of the form `<pkg>[@version] +var1 var2=val ...`

Compilers are specified separately via the `-C`/`--compiler` option
(e.g. `-C gcc@14.1.0`).  Dependency constraints are specified via the
`-d`/`--dependency` option (e.g. `--dependency 'root %gcc@11'`).

Currently supported positional variants are @-prefixed version strings,
Boolean variants, and key-value pair variants. Also
supported are propagated variants, where two syntactic tokens are
specified instead of one (e.g. `++var1` and `cxxstd==20` vs. `+var1`
and `cxxstd=20`).  In addition, it is possible to specify virtual
packages using the notation (e.g.) `^[virtuals=tbb] intel-tbb-oneapi`,
where `tbb` is the virtual package provided by the concrete package
`intel-tbb-oneapi`.

## From an existing set of repositories

Suppose I have a directory `test-devel` that contains a subdirectory `srcs`:

```console
$ pwd
/home/knoepfel/scratch/test-devel
$ ls srcs/
cetlib  cetlib-except  hep-concurrency
```

The entries in `srcs` are the repositories I wish to develop.  I then
create an MPD project in the `test-devel` directory by invoking:

```console
$ spack mpd new-project --name test -E gcc-14-1 -C gcc@14.1.0 cxxstd=20

==> Creating project: test

  Project directories:
    top     /scratch/knoepfel/test-devel
    build   /scratch/knoepfel/test-devel/build
    local   /scratch/knoepfel/test-devel/local
    sources /scratch/knoepfel/test-devel/srcs

  Packages to develop:
    cetlib @develop cxxstd=20 generator=make %gcc@14.1.0
    cetlib-except @develop cxxstd=20 generator=make %gcc@14.1.0
    hep-concurrency @develop cxxstd=20 generator=make %gcc@14.1.0
```

The command-line variant `cxxstd=20` has been applied to any package
under development that supports it.  The compiler specified via `-C
gcc@14.1.0` has also been applied to each package, as has the default
generator `make`.

> [!NOTE]
> The expression
>
> ```console
>     cetlib@develop cxxstd=20 generator=make %gcc@14.1.0
> ```
>
> is a specification that Spack **assumes** when creating and
> concretizing the project's environment.  The `cetlib` code under
> development, however, does not necessarily need to correspond to the
> `develop` branch.  The developer is permitted to change Git branches
> within the repository so long as the provided dependencies satisfy
> the needs of the code under development.

### Project concretization

The next step is concretization, where Spack searches for a valid
combination of all dependencies required for developing the specified
packages.  The dependencies are specified in each package's Spack
recipe, which Spack consults *along with* the dependencies already
specified in the provided environment (`gcc-14-1-0` in this example)
and on the command line.  The printout to the terminal will look like:

```console
==> Determining dependencies (this may take a few minutes)
==> Creating initial environment
⋮
==> Creating local development environment
⋮
==> Adjusting specifications for package development
⋮
==> Finalizing concretization
⋮
```

Concretization begins by creating an initial environment named after
the MPD project (in this case `test`).  Assuming the named environment
concretizes successfully, the environment is then copied to a local
environment (located in an MPD project's `<top-level dir>/local`
directory), which is then adjusted for development.  It is this local
environment that will be used (usually implicitly) when invoking the
`spack mpd build` and `spack mpd test` commands.

### Installing the project's development environment

Once the concretization steps finish, you may need to install some
packages before proceeding with development.  If so, you will be asked
if you wish to continue with the installation (default is "yes", so
pressing `return` is sufficient).  Upon answering "yes", you will be
asked how many cores to use (default is half of the total number of
cores as specified by the command `nproc`):

```
==> Would you like to continue with installation? [Y/n]
==> Specify number of cores to use (default is 12)
```

The installation step involves installing the required dependencies as
well as the local development environment:

```console
==> Installing development environment

[+] /usr (external glibc-2.34-hjl43avhawltutkgujn2ns3577kjowlq)
[+] /usr (external glibc-2.34-smaln5legoyu46un62ag5l6uzp6lzrpv)
[+] /usr (external curl-7.76.1-vzpy2tfjkkyvweh2muty6lqxb6fvfcp6)
[+] /usr (external gmake-4.3-2cb6rxkmbq3tcvqen664riv3mr4bit6d)
[+] /usr (external openssl-3.0.7-wl62it2i7iliquqoaoqbpjz735u7ytpo)
⋮

==> test is ready for development (e.g type spack mpd build ...)
```

You may now invoke `spack mpd build`, `spack mpd test`, and `spack mpd
install`.

## From an empty set of repositories

If you do not have any repositories listed in your project's sources
directory, you can still create an MPD project:

```console
$ ls srcs/
(empty)
$ spack mpd new-project --name test -C gcc@14.1.0 cxxstd=20

==> Creating project: test

  Project directories:
    top     /scratch/knoepfel/test-devel
    build   /scratch/knoepfel/test-devel/build
    local   /scratch/knoepfel/test-devel/local
    sources /scratch/knoepfel/test-devel/srcs

==> You can clone repositories for development by invoking

  > spack mpd git-clone --suites <suite name>

  (or type 'spack mpd git-clone --help' for more options)
```

After [cloning some
repositories](Helpers.md#cloning-repositories-to-develop), you may
refresh the project to proceed with concretization:

```console
$ spack mpd git-clone --fork cetlib cetlib-except hep-concurrency

==> Cloning and forking:

  cetlib .................. done   (cloned, added fork knoepfel/cetlib)
  cetlib-except ........... done   (cloned, created fork knoepfel/cetlib-except)
  hep-concurrency ......... done   (cloned, created fork knoepfel/hep-concurrency)

==> You may now invoke:

  spack mpd refresh
```

Upon invoking `refresh` you will then see printout that is very
similar to what is [mentioned above when developing from an existing
set of repositories](#from-an-existing-set-of-repositories) .  The
`refresh` command accepts any of the [variants mentioned
above](#variant-support).  Any variants provided will be added to (or
override) the set of constraints the concretizer must honor.

## Missing intermediate dependencies

Consider three packages——*A*, which depends on *B*, which depends on
*C*.  Of the three packages, *B* is the intermediate dependency: it
depends on *C* and serves as a dependency of *A*.  Suppose a user only
wants to develop *A* and *C*.  If *A* is rebuilt based on changes made
in *C*, binary incompatibilities and unexpected behavior may result if
*B* is not also rebuilt.  In such a case *B* is a missing intermediate
dependency and considered an error.

MPD will detect missing intermediate dependencies (like *B* above)
that should be rebuilt whenever the developed packages (like *A* and
*C* above) are adjusted.  Of the three packages above (`cetlib`,
`cetlib-expect`, and `hep-concurrency`), `hep-concurrency` is the
intermediate package.  If `hep-concurrency` were removed from the
development list, you would see the following upon invoking
`new-project` (or `refresh`):

```console
$ spack mpd git-clone cetlib cetlib-except

==> Cloning:

  cetlib .................. done    (cloned)
  cetlib-except ........... done    (cloned)

⋮

$ spack mpd refresh

⋮

==> Error: The following packages are intermediate dependencies of the
currently cloned packages and must also be cloned:

 - hep-concurrency (depends on cetlib-except)
```
