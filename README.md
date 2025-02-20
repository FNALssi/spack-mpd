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
   1. For developers of packages that depend on SciSoft software, we
      recommend you clone the Fermilab fork of Spack using our bootstrap script:
      
      ```console
      wget https://github.com/FNALssi/fermi-spack-tools/raw/refs/heads/fnal-develop/bin/bootstrap
      bash bootstrap $PWD/spack```

     or you can directly git clone it: `git clone https://github.com/FNALssi/spack.git`, and add repositories per item 4., below.

   2. _You are encouraged to [chain upstream Spack installations](https://spack.readthedocs.io/en/latest/chain.html) to your own installation to avoid unnecessary building, installation, and wasted disk space._
2. Invoke `source <your spack installation>/share/spack/setup-env.sh`.
3. Each package to be developed must have:
   1.  An accessible [Spack recipe](https://spack.readthedocs.io/en/latest/packaging_guide.html).  To verify this, you should see the package listed when typing `spack list <package name>`.
   2.  A `develop` version (assumes an accessible Spack recipe).  To verify this, you should see `develop` listed as a supported version when typing `spack info <package name>`.
4. Developers of SciSoft-provided software (`art`, `larreco`, `nusimdata`, etc.) should make sure they clone the Fermilab-managed Spack recipes; the bootstrap script, above does this for you, but 
    ```console
    $ cd <some dir>
    $ git clone https://github.com/FNALssi/fnal_art.git
    $ git clone https://github.com/NuSoftHEP/nusofthep-spack-recipes.git
    $ git clone https://github.com/LArSoft/larsoft-spack-recipes.git
    $ spack repo add fnal_art
    $ spack repo add nusofthep-spack-recipes
    $ spack repo add larsoft-spack-recipes
    ```

## Using MPD

0. [Installation](doc/Installation.md) (do this first)
1. [Initialization](doc/Initialization.md) (do this second)
2. [Creating a project](doc/Creation.md) (skip if you do not need a new project)
3. [Project selection and environment activation](doc/Selection.md)
4. [Building a project](doc/Building.md)
5. [Installing a project](doc/Project_installation.md)
6. [Zapping a project](doc/Zapping.md)
7. [Removing a project](doc/Removing.md)
8. Helper commands
   1. [MPD status](doc/Helpers.md#status)
   2. [Cloning repositories to develop](doc/Helpers.md#cloning-repositories-to-develop)
   3. [Listing projects](doc/Helpers.md#listing-available-projects)

## Limitations

As of now, MPD can only support the development of CMake-based
packages.  There are currently no plans to support other build
systems.
