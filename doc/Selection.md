# Project selection and environment activation

To develop packages, you must use select an MPD project.

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

## Activating a Spack environment
