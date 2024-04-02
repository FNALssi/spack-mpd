# Helper commands

## Cloning repositories to develop

MPD supports cloning *read-only* git repositories into a selected
project's source directory.  The help message for the `spack mpd
git-clone` command is:

```console
$ spack mpd g -h
usage: spack mpd git-clone [-h] [--help-repos | --help-suites | --suite <suite name>] [<repo spec> ...]

clone git repositories for development

positional arguments:
  <repo spec>           a specification of a repository to clone. The repo spec may either be:
                        (a) any repository name listed by the --help-repos option, or
                        (b) any URL to a Git repository.

optional arguments:
  --help-repos          list supported repositories
  --help-suites         list supported suites
  --suite <suite name>  clone repositories corresponding to the given suite name
  -h, --help            show this help message and exit
```

A `repo spec` can be:

- any repository name listed by the `spack mpd --help-repos` option, or
- any URL to a Git repository.

> [!WARNING]
> 1. When using `spack mpd g <repository name>`, the cloned repository
>    will be read-only (i.e. no pushes allowed to the remote
>    repository).  Users who would like to clone repositories with
>    write permissions should use the corresponding repository URL
>    (e.g. `spack mpd g git@github.com/Org/RepoName.git`).
> 2. `spack mpd g` does not yet support forking of GitHub
>    repositories.  If this is desired, users should use the [GitHub
>    CLI](https://cli.github.com) directly.  A feature request could
>    also be made of `spack-mpd`.

After cloning any repositories into your selected project's source
directory, be sure to refresh the project (`spack mpd refresh`), which
will recreate the Spack environment to reflect the changes.

## Listing projects

You can list the existing MPD projects by invoking `spack mpd list`:

```console
$ spack mpd ls -h
usage: spack mpd list [-h] [-t <project name> | -b <project name> | -s <project name>] [<project name> ...]

list MPD projects

When no arguments are specified, prints a list of existing MPD projects
and the status of their corresponding Spack environments.

positional arguments:
  <project name>        print details of the MPD project

optional arguments:
  -b <project name>, --build <project name>
                        print build-level directory for project
  -h, --help            show this help message and exit
  -s <project name>, --source <project name>
                        print source-level directory for project
  -t <project name>, --top <project name>
                        print top-level directory for project
```

As stated in the help text, invoking `spack mpd list` with no options
prints a table of existing projects with the status of their
corresponding environments:

```console
$ spack mpd ls

==> Existing MPD projects:

   Project name    Environment status
   ------------    ------------------
   art-devel       installed
 ▶ test            installed

```

The right-pointing triangle `▶` denotes the selected project for the
shell session.  Projects with a preceding left-pointing triangle `◀`
indicate projects that are active in other shell sessions:

```console
$ spack mpd ls

==> Existing MPD projects:

   Project name    Environment status
   ------------    ------------------
   art-devel       installed
 ◀ test            installed

```

This can be helpful in determining whether you should select a project
in your current shell session, or whether you should find the shell
with the project that's already selected.  Having two or more shell
sessions with the same project selected can lead to one shell
overwriting another.

If two or more shells have selected the same MPD project, a warning will be printed to the screen:

```console
$ spack mpd ls

==> Existing MPD projects:

   Project name    Environment status
   ------------    ------------------
   art-devel       installed
 ▶ test            installed           Warning: used by more than one shell

```

Destroying (or invoking `spack mpd clear`) on all but one of those shells will remove the warning.

### Listing project details

Details of a specific project will be printed to the screen if the project name is provided as a positional argument:

```console
$ spack mpd ls test

==> Details for test

name: test
top: /scratch/knoepfel/test-devel
source: /scratch/knoepfel/test-devel/srcs
build: /scratch/knoepfel/test-devel/build
local: /scratch/knoepfel/test-devel/local
install: /scratch/knoepfel/test-devel/local/install
envs:
- gcc-13-2-0
packages:
- cetlib
- cetlib-except
- hep-concurrency
compiler: gcc@13.2.0
cxxstd: '20'
variants: ''
status: installed

```

### Listing project directories

Sometimes it is helpful for just the path of one of the project's
directories to be printed:

```console
$ spack mpd ls --source test
/scratch/knoepfel/test-devel/srcs
$ cd $(spack mpd ls --source test)
(Now in test source directory)
```

This is particularly convenient when logging in to the system and
wanting to begin development immediately:

```console
$ spack env activate test
(Spack environment test now active; MPD project test now selected)
$ cd $(spack mpd ls --build test)
(Now in test build directory)
$ ninja
```
