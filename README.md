# MPD

MPD (for <b><i>m</i></b>ulti-<b><i>p</i></b>ackage
<b><i>d</i></b>evelopment) is a Spack extension that allows users to
develop CMake-based packages in concert with Spack-provided external
software.  It is not the same as [`spack
develop`](https://spack.readthedocs.io/en/latest/environments.html#developing-packages-in-a-spack-environment),
which Spack provides to support development of any Spack package.
Although `spack develop` makes it easy to propagate development
changes to a full Spack installations, `spack develop` does not lend
itself well to the iterative development Fermilab IF users usually
practice (tweak source code, build, test, then repeat).  The purpose
of MPD is to satisfy the iterative development needs of our users and
developers.

## Prerequisites

1. You must be able to write to the Spack installation that you set up.
   1. For developers of packages that depend on SciSoft software, you should clone the Fermilab fork of Spack `git clone https://github.com/FNALssi/spack.git`.
   2. _You are encouraged to [chain upstream Spack installations](https://spack.readthedocs.io/en/latest/chain.html) to your own installation to avoid unnecessary building, installation, and wasted disk space._
3. Each package to be developed must have a [Spack recipe](https://spack.readthedocs.io/en/latest/packaging_guide.html).
4. Install `spack-mpd`.

## Using MPD

0. [Installation](doc/Installation.md) (do this first)
1. [Initialization](doc/Initialization.md) (do this second)
2. [Project selection and environment activation](doc/Selection.md)
3. [Creating a project](doc/Creation.md)
4. [Building a project](doc/Building.md)
5. [Zapping a project](doc/Zapping.md)
6. [Removing a project](doc/Removing.md)
7. Helper commands
   1. [Cloning repositories to develop](doc/Helpers.md#cloning-repositories-to-develop)
   2. [Listing projects](doc/Helpers.md#listing-available-projects)

## Limitations

As of now, MPD can only support the development of CMake-based
packages.  There are currently no plans to support other build
systems.
