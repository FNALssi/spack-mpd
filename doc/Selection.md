# Project selection and environment activation

Each MPD project (see [Creating a project](doc/Creation.md)) has an
associated Spack environment with the same name as the project name.
Depending on which `spack mpd` command is invoked, there are varying
requirements on whether an MPD project must be selected and a Spack
environment activated.  The following chart summarizes these
requirements:

- The white check mark :white_check_mark: indicates what is required
  to invoke the command (i.e. `spack mpd build` requires MPD to be
  initialized and a selected project).
- The :x: symbol indicates what is forbidden in order to invoke the
  command (i.e. `spack mpd rm-project` requires MPD to be initialized,
  forbids that a project is selected, and forbids that an environment
  is active).
- Table cells with no symbol indicate that the command can be invoked
  irrespective of whether the requirement is satisfied or not.

| Command | MPD initialized | Selected project | Active environment |
| --- | :---: | :---: | :---: |
| `spack mpd init` | | | |
| `spack mpd list` | :white_check_mark: | | |
| `spack mpd new-project` | :white_check_mark: | | :x: |
| `spack mpd select` | :white_check_mark: | | :x: |
| `spack mpd clear` | :white_check_mark: | | :x: |
| `spack mpd git-clone` | :white_check_mark: | :white_check_mark: | |
| `spack mpd refresh` | :white_check_mark: | :white_check_mark: | :x: |
| `spack mpd zap` | :white_check_mark: | :white_check_mark: | |
| `spack mpd build` | :white_check_mark: | :white_check_mark: | |
| `spack mpd install` | :white_check_mark: | :white_check_mark: | |
| `spack mpd test` | :white_check_mark: | :white_check_mark: | |
| `spack mpd rm-project` | :white_check_mark: | :x: [^1] | :x: |

[^1]: Without `--force`, `rm-project` requires that no project is selected. With `--force`, a selected project is permitted.

## Selecting a project

The following actions will select a project

1. Creating a new project via `spack mpd new-project ...` will
   automatically select the project after it has been created.
2. Activating a Spack environment with a given name will automatically
   select the corresponding project.
3. Explicitly invoking `spack mpd select`:
   1. `spack mpd select -p <project>` will select the specified project by name, assuming it exists.
   2. `spack mpd select <top-level directory of project>` will select the project corresponding to the specified directory.
   3. `spack mpd select` (with no arguments) will (a) provide a menu of existing MPD projects and allow you to specify which one you would like to select, or (b) select the only MPD project if only one exists.

You can tell which project is selected by invoking `spack mpd
list`---the selected project is indicated with a right-pointing
triangle `▶`.

```console
$ spack mpd list

==> Existing MPD projects:

   Project name    Sources directory
   ------------    -----------------
   nu-devel        /scratch/knoepfel/nu-devel/srcs
 ▶ art-devel       /scratch/knoepfel/art-devel/srcs

```

## Clearing (deselecting) a project

To deselect a project, the user invokes `spack mpd clear`.  You can
verify the project has been cleared by invoking `spack mpd list`---you
should no longer see any right arrow `▶` indicator.

```console
$ spack mpd list

==> Existing MPD projects:

   Project name    Sources directory
   ------------    -----------------
   nu-devel        /scratch/knoepfel/nu-devel/srcs
   art-devel       /scratch/knoepfel/art-devel/srcs
```

> [!WARNING]
> Deactivating a Spack environment does **not** clear the project.
> This makes it possible to continue to interacting with the project
> (e.g. invoking `spack mpd git-clone`) when an active environment is
> no longer needed or desired.

## Selecting a project in use by another shell

It is possible for more than one shell to select the same project.
However, a warning will be printed to the screen whenever this
happens:

```console
$ spack mpd select art-devel
==> Warning: Project art-devel selected in another shell.  Use with caution.
```

The project list will also reflect if more than one shell have
selected the same project:

```console
$ spack mpd list

==> Existing MPD projects:

   Project name    Sources directory
   ------------    -----------------
   nu-devel        /scratch/knoepfel/nu-devel/srcs
 ▶ art-devel       /scratch/knoepfel/art-devel/srcs           Warning: used by more than one shell
```

## Activating a Spack environment

To build, install, or test any of the packages under development, the
Spack environment corresponding to the project must be active.  This
is achieved by invoking `spack env activate <project>`.

> [!TIP]
> Activating a Spack environment automatically selects the
> corresponding MPD project.  Users therefore do **not** need to
> invoke `spack mpd select <project>` before invoking `spack env
> activate <project>`.
