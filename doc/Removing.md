# Removing a project

After developing a set of packages, the project can be removed from
MPD using `spack mpd rm <project name>`.  Invoking this command will:

- remove the project entry from the list printed by `spack mpd list`,
- delete the build, local, and `.mpd` metadata directories from the top-level
  directory, and
- uninstall the project's environment.

Note that the sources directory and top-level directory will *not* be
removed.

Before deleting anything, MPD compares the departing project's managed
directories with every path owned or referenced by remaining projects. If any
paths overlap, MPD unregisters the project and clears all of its shell-selection
tokens, but preserves all three managed directories. The command reports the
preserved paths so they can be inspected and cleaned up manually. Cleanup is
all-or-nothing in an unsafe legacy layout.

To remove the project, the project must not be selected, and its
environment must be deactivated.  This can be accomplished by the
following commands:

```console
$ spack env deactivate
$ spack mpd clear
$ spack mpd rm-project <project name>
```

The last two commands can be combined so that the following is equivalent:

```console
$ spack env deactivate
$ spack mpd rm-project -f <project name>
```
