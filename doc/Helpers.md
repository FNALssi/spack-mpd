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
usage: spack mpd git-clone [-h] [--suites <suite name> [<suite name> ...]]
                           [--add-suite <suite YAML file> [<suite YAML file> ...]]
                           [--remove-suite <suite name> [<suite name> ...]]
                           [--fork | --help-repos | --help-repos-with-urls | --help-suites | --help-suites-with-paths]
                           [<repo spec> ...]

clone git repositories for development

positional arguments:
  <repo spec>           a specification of a repository to clone. The repo spec may either be:
                        (a) any repository name listed by the --help-repos option, or
                        (b) any URL to a Git repository.

optional arguments:
  --suites <suite name> [<suite name> ...]
                        clone repositories corresponding to the given suite name (multiple allowed)
  --add-suite <suite YAML file> [<suite YAML file> ...]
                        add one or more suite-definition YAML files
  --remove-suite <suite name> [<suite name> ...]
                        remove one or more known suites by name
  --fork                fork GitHub repository or set origin to already forked repository
  --help-repos          list known repositories
  --help-repos-with-urls
                        list known repositories with full URLs
  --help-suites         list known suites
  --help-suites-with-paths
                        list known suites and suite YAML file paths
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

### Suites

A _suite_ is a named collection of repositories that can be cloned
together.  You can list the known suites and the repositories they
contain with `--help-suites`:

```console
$ spack mpd git-clone --help-suites

==> Known suites:

  critic
    - art, art-root-io, canvas, canvas-root-io, cetlib, cetlib-except,
      critic, fhicl-cpp, fhicl-py, gallery, hep-concurrency, messagefacility
  ⋮
```

Use `--help-suites-with-paths` to additionally print the path to the
YAML file that defines each suite.  Once you know a suite's name, you
can clone all of its repositories at once:

```console
$ spack mpd git-clone --suites critic
```

#### Adding and removing suites

MPD ships with a set of built-in suites, but you can define your own.
A suite-definition file must be named `<something>-suite.yaml` and
contain exactly one top-level suite mapping, for example:

```yaml
# my-suite.yaml
my:
  gh_org_name: art-framework-suite
  repos:
    - cetlib
    - cetlib-except
    - hep-concurrency
```

- `gh_org_name` is the GitHub organization used to construct the clone
  URL for each repository (i.e. `https://github.com/<gh_org_name>/<repo>.git`).
- `repos` is the list of repositories that make up the suite.

Register the suite with the `--add-suite` option, which copies the YAML
file into MPD's known-suites directory:

```console
$ spack mpd git-clone --add-suite my-suite.yaml

==> Added suite my from my-suite.yaml
```

If a suite file with the same name already exists, you will be prompted
before it is overwritten.  Because `--add-suite` is processed before any
clone operations, you can add and use a suite in a single invocation:

```console
$ spack mpd git-clone --add-suite my-suite.yaml --suites my
```

To remove a known suite by name, use `--remove-suite` (you will be
prompted for confirmation):

```console
$ spack mpd git-clone --remove-suite my

==> Removed suite my from .../var/mpd/known_suites/my-suite.yaml
```

> [!NOTE]
> Adding or removing a suite only requires MPD to be initialized——a
> project need not be selected.  Cloning repositories (via `<repo spec>`
> or `--suites`), however, does require a selected project.

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
