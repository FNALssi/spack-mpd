# Spack MPD

Spack MPD is a Spack extension that allows users to develop CMake-based packages in concert with Spack-provided external software.  It is not the same as [`spack develop`](https://spack.readthedocs.io/en/latest/environments.html#developing-packages-in-a-spack-environment), which Spack provides to support development of any Spack package.  Although `spack develop` makes it easy to propagate development changes to a full Spack installations, `spack develop` does not lend itself well to the iterative development Fermilab IF users usually practice (tweak source code, build, test, then repeat).  The purpose of Spack MPD is to satisfy the iterative development needs of our users and developers.

## Prerequisites

1. You must be able to write to the Spack installation that you set up.
    - _You are encouraged to [chain upstream Spack installations](https://spack.readthedocs.io/en/latest/chain.html) to your own installation to avoid unnecessary building, installation, and wasted disk space._
2. Each package to be developed must have a [Spack recipe](https://spack.readthedocs.io/en/latest/packaging_guide.html).
3. Install Spack-MPD.

## Using MPD

1. Initialization (once per system)
2. Activating an existing project (frequent)
3. Creating a new project
4. Building a project
5. Cleaning/zapping a project
6. Removing a project
7. Helper commands
   1. Cloning repositories to develop
   2. Listing projects

## Limitations

As of now, Spack MPD can only support the development of CMake-based packages.  There are currently no plans to support other build systems.
