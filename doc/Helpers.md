# Helper commands

## Status

The helper command `spack mpd status` lists the selected project (if
any), its development status, and when it was last installed.  For
example:

```console
$ spack mpd status
==> Selected project:   test
    Development status: ready
    Last installed:     2024-12-02 15:30:44
```

Development status values include:

- _**created**_: the initial project environment has been created as
  part of the `new-project` or `refresh` commands,
- _**concretized**_: the named project environment and the
  corresponding local development environment have been fully
  concretized, but neither has been fully installed.
- _**ready**_: the local development environment has been installed,
  signifying that the standard MPD development commands (e.g. `spack
  mpd build`) can be invoked.

If a project's named environment has not yet been installed (or has
been uninstalled via an MPD `zap` command), the last-installed date
will read as three hyphens `---`.

## Cloning repositories to develop

MPD supports cloning *read-only* git repositories into a selected
project's source directory.  The help message for the `spack mpd
git-clone` command is:

```console
$ spack mpd git-clone -h
usage: spack mpd git-clone [-h] [--suites <suite name> [<suite name> ...]] [--fork | --help-repos | --help-suites]
                           [<repo spec> ...]

clone git repositories for development

positional arguments:
  <repo spec>           a specification of a repository to clone. The repo spec may either be:
                        (a) any repository name listed by the --help-repos option, or
                        (b) any URL to a Git repository.

optional arguments:
  --fork                fork GitHub repository or set origin to already forked repository
  --help-repos          list supported repositories
  --help-suites         list supported suites
  --suites <suite name> [<suite name> ...]
                        clone repositories corresponding to the given suite name (multiple allowed)
  -h, --help            show this help message and exit
```

A `repo spec` can be:

- any repository name listed by the `spack mpd git-clone --help-repos` option, or
- any URL to a Git repository.

> [!WARNING]
> When using `spack mpd git-clone <repository name>`, the cloned repository
> will be read-only (i.e. no pushes allowed to the remote
> repository).  Users who would like to clone repositories with
> write permissions should use the corresponding repository URL
> (e.g. `spack mpd git-clone git@github.com/Org/RepoName.git`).

After cloning any repositories into your selected project's source
directory, be sure to refresh the project (`spack mpd refresh`), which
will recreate the Spack environment to reflect the changes.

## Listing projects

You can list the existing MPD projects by invoking `spack mpd list`:

```console
$ spack mpd list -h
usage: spack mpd list [-h] [--raw] [-t <project name> | -b <project name> | -s <project name>] [<project name> ...]

list MPD projects

When no arguments are specified, prints a list of existing MPD projects
and their corresponding sources directories.

positional arguments:
  <project name>        print details of the MPD project

optional arguments:
  --raw                 print YAML configuration of the MPD project
                        (used only when project name is provided)
  -b <project name>, --build <project name>
                        print build-level directory for project
  -h, --help            show this help message and exit
  -s <project name>, --source <project name>
                        print source-level directory for project
  -t <project name>, --top <project name>
                        print top-level directory for project
```

As stated in the help text, invoking `spack mpd list` with no options
prints a table of existing projects with their sources directories:

```console
$ spack mpd ls

==> Existing MPD projects:

   Project name    Sources directory
   ------------    -----------------
   meld-devel      /scratch/knoepfel/meld-devel/srcs
 ▶ test            /scratch/knoepfel/test-devel/srcs

```

The right-pointing triangle `▶` denotes the selected project for the
shell session.  Projects with a preceding left-pointing triangle `◀`
indicate projects that are active in other shell sessions:

```console
$ spack mpd ls

==> Existing MPD projects:

   Project name    Sources directory
   ------------    -----------------
   meld-devel      /scratch/knoepfel/meld-devel/srcs
 ◀ test            /scratch/knoepfel/test-devel/srcs

```

This can be helpful in determining whether you should select a project
in your current shell session, or whether you should find the shell
with the project that's already selected.  Having two or more shell
sessions with the same project selected can lead to one shell
overwriting another.

If two or more shells have selected the same MPD project, a warning
will be printed to the screen:

```console
$ spack mpd ls

==> Existing MPD projects:

   Project name    Sources directory
   ------------    -----------------
   meld-devel      /scratch/knoepfel/meld-devel/srcs
 ▶ test            /scratch/knoepfel/test-devel/srcs               Warning: used by more than one shell

```

Closing (or invoking `spack mpd clear` on) all but one of those shells
will remove the warning.

### Listing project details

Details of a specific project will be printed to the screen if the
project name is provided as a positional argument:

```console
$ spack mpd list --raw test

==> Details for test

name: test
envs:
- gcc-14-1
top: /scratch/knoepfel/test-devel
source: /scratch/knoepfel/test-devel/srcs
build: /scratch/knoepfel/test-devel/build
local: /scratch/knoepfel/test-devel/local
compiler:
  value: gcc@14.1.0
  variant: '%gcc@14.1.0'
cxxstd:
  value: '20'
  variant: cxxstd=20
generator:
  value: make
  variant: generator=make
variants: cxxstd=20 %gcc@14.1.0
packages:
  cetlib-except:
    require:
    - '@develop'
    - '%gcc@14.1.0'
    - cxxstd=20
    - generator=make
  cetlib:
    require:
    - '@develop'
    - '%gcc@14.1.0'
    - cxxstd=20
    - generator=make
  hep-concurrency:
    require:
    - '@develop'
    - '%gcc@14.1.0'
    - cxxstd=20
    - generator=make
dependencies: {}
status: ready
installed: '---'

```

### Listing project directories

Sometimes it is helpful for just the path of one of the project's
directories to be printed:

```console
$ spack mpd list --source test
/scratch/knoepfel/test-devel/srcs
$ cd $(spack mpd ls --source test)
(Now in test source directory)
```

This is particularly convenient when logging in to the system and
wanting to invoke generator commands (e.g. `ninja`) immediately:

```console
$ spack env activate test
(Spack environment test now active; MPD project test now selected)
$ cd $(spack mpd list --build test)
(Now in test build directory)
$ ninja
```
