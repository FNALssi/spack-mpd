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
$ spack mpd n --help
usage: spack mpd new-project [-hf] --name NAME [-T TOP] [-S SRCS] [-E ENV] [variants ...]

create MPD development area

positional arguments:
  variants

optional arguments:
  --name NAME           (required)
  -E ENV, --env ENV     environments from which to create project
                        (multiple allowed)
  -S SRCS, --srcs SRCS  directory containing repositories to develop
                        (default: /scratch/knoepfel/art-devel/srcs)
  -T TOP, --top TOP     top-level directory for MPD area
                        (default: /scratch/knoepfel/art-devel)
  -f, --force           overwrite existing project with same name
  -h, --help            show this help message and exit
```

A few observations:

- The only required program option is `--name` which, because of
  quirks of the `argparse` technology that parses Spack commands, is
  listed either as an "optional argument" or an "option".  The other
  program options are not mandated as defaults are provided by MPD.

- The default top-level directory of your MPD project is the current
  working directory (the one in which you invoke `spack mpd
  new-project`).  Unless specified otherwise, the sources directory
  will be a subdirectory of the top-level directory.

## From an existing set of repositories

Suppose I have a directory `test-devel` that contains a subdirectory `srcs`:

```console
$ pwd
/home/knoepfel/scratch/test-devel
$ ls srcs/
cetlib  cetlib-except  hep-concurrency
```

The entries in `srcs` are the repositories I wish to develop.  I then create an MPD project in the `test-devel` directory by invoking:

```console
$ spack mpd n --name test -E gcc-13-2-0 cxxstd=20 %gcc@13.2.0

==> Creating project: test

Using build area: /scratch/knoepfel/test-devel/build
Using local area: /scratch/knoepfel/test-devel/local
Using sources area: /scratch/knoepfel/test-devel/srcs

  Will develop:
    - cetlib
    - cetlib-except
    - hep-concurrency

==> Concretizing project (this may take a few minutes)
==> Environment test has been created
==> Updating view at /scratch/knoepfel/spack/var/spack/environments/test/.spack-env/view
==> Warning: Skipping external package: cmake@3.28.3%gcc@13.2.0~doc+ncurses+ownlibs build_system=generic build_type=Release arch=linux-almalinux9-cascadelake/gykagno
==> Warning: Skipping external package: gmake@4.3%gcc@13.2.0~guile build_system=generic patches=599f134 arch=linux-almalinux9-cascadelake/qzjvjvx
==> Concretization complete

==> Ready to install MPD project test

==> Would you like to continue with installation? [Y/n] 
==> Specify number of cores to use (default is 12) 
==> Installing test
==> All of the packages are already installed

==> MPD project test has been installed.  To load it, invoke:

  spack env activate test

```

## From an empty set of repositories

```console
$ ls
(empty)
$ spack mpd n --name test cxxstd=20 %gcc@13.2.0

==> Creating project: test

Using build area: /scratch/knoepfel/test-devel/build
Using local area: /scratch/knoepfel/test-devel/local
Using sources area: /scratch/knoepfel/test-devel/srcs

==> You can clone repositories for development by invoking

  spack mpd g --suite <suite name>

  (or type 'spack mpd g --help' for more options)

$ spack mpd g cetlib cetlib-except hep-concurrency

==> The following repositories have been cloned:

  - cetlib
  - cetlib-except
  - hep-concurrency

==> You may now invoke:

  spack mpd refresh
```

## Concretization

## Missing intermediate dependencies

Consider three packages——*A*, which depends on *B*, which depends on *C*.  Of the three packages, *B* is the intermediate dependency: it depends on *C* and serves as a dependency of *A*.  Suppose a user only wants to develop *A* and *C*.  If *A* is rebuilt based on changes made in *C*, binary incompatibilities and unexpected behavior may result if *B* is not also rebuilt.  In such a case *B* is a missing intermediate dependency and considered an error.

MPD will detect missing intermediate dependencies (like *B* above) that should be rebuilt whenever the developed packages (like *A* and *C* above) are adjusted.  Of the three packages above (`cetlib`, `cetlib-expect`, and `hep-concurrency`), `hep-concurrency` is the intermediate package.  If `hep-concurrency` were removed from the development list, you would see the following upon invoking `new-project` (or `refresh`):

```console
$ spack mpd g cetlib cetlib-except
                                                                    
==> The following repositories have been cloned:               
                                                                     
  - cetlib                                                            
  - cetlib-except

...

$ spack mpd refresh

...

==> Error: The following packages are intermediate dependencies of the
currently cloned packages and must also be cloned:

 - hep-concurrency (depends on cetlib-except)

```

