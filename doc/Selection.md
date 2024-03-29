# Project selection and environment activation

MPD organizes development efforts into *projects*.

## Selecting a project

The following actions will select a project

1. Creating a new project via `spack mpd new-project ...` will
   automatically select the project after it has been created.
2. Activating a Spack environment with a given name will automatically
   select the corresponding project.
3. Explicitly invoking `spack mpd select <project>` will select the
   specified project, assuming it is exists.

## Clearing (deselecting) a project

To deselect a project, the user invokes `spack mpd clear`.

>[!WARNING]
> Deactivating a Spack environment does **not** clear the project.  This makes it
> possible to continue to interacting with the project (e.g. invoking
> `spack mpd git-clone`) when an active environment is no longer needed or desired.

## Activating a Spack environment

To build, install, or test any of the packages under development, the Spack environment corresponding to the project must be active.  This is achieved by invoking `spack env activate <project>`.

## Selection requirements for MPD commands

In the following chart, the white check mark :white_check_mark: indicates what must be satisfied to invoke the command (i.e. `spack mpd build` requires both a selected project and an active environment).  The :x: symbol indicates what must **not** be satisfied to invoke the command (i.e. `spack mpd rm-project` requires that no project is selected and no environment is active).  Table cells with no symbol indicate that the command can be invoked irrespective of whether the requirement is satisfied or not.

| Command | Selected project | Active environment |
| --- | :---: | :---: |
| `spack mpd clear` | | |
| `spack mpd init` | | |
| `spack mpd list` | | |
| `spack mpd new-project` | | |
| `spack mpd select` | | |
| `spack mpd git-clone` | :white_check_mark: | |
| `spack mpd refresh` | :white_check_mark: | |
| `spack mpd zap` | :white_check_mark: | |
| `spack mpd build` | :white_check_mark: | :white_check_mark: |
| `spack mpd install` | :white_check_mark: | :white_check_mark: |
| `spack mpd test` | :white_check_mark: | :white_check_mark: |
| `spack mpd rm-project` | :x: | :x: |

