# Creating an MPD project

An MPD project consists of:

- A name to distinguish it from other MPD projects.

- A top-level directory, which will contain (at a minimum) two
  subdirectories created by MPD: `build` and `local`.

- A sources directory, which contains (symbolic links to) CMake-based
  repositories to be developed.

There are two different ways to create an MPD project:

1. From an existing set of repositories that you would like to develop
2. From an empty set of repositories that you wish to MPD to populate by `git`-cloning repositories

Both approaches are supported through the `spack mpd new-project` command:

```console
$ spack mpd n --help
usage: spack mpd new-project [-hf] --name NAME [-T TOP] [-S SRCS] [-E ENV] [variants ...]

create MPD development area

positional arguments:
  variants

optional arguments:
  --name NAME           (required)
  -E ENV, --env ENV     environments from which to create project
                        (multiple allowed)
  -S SRCS, --srcs SRCS  directory containing repositories to develop
                        (default: /scratch/knoepfel/art-devel/srcs)
  -T TOP, --top TOP     top-level directory for MPD area
                        (default: /scratch/knoepfel/art-devel)
  -f, --force           overwrite existing project with same name
  -h, --help            show this help message and exit
```

A few observations:

- The only required program option is `--name` which, because of
  quirks of the `argparse` technology used to parse Spack commands, is
  listed either as an "optional argument" or an "option".  The other
  program options are not mandated as defaults are provided by MPD.

- The default top-level directory of your MPD project is the current
  working directory (the one in which you invoke `spack mpd
  new-project`).  Unless specified otherwise, the sources directory
  will be a subdirectory of the top-level directory.

## From an existing set of repositories

## From an empty set of repositories
