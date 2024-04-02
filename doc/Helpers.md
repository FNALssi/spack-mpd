# Helper commands

## Listing available projects

## Cloning repositories to develop

MPD supports cloning *read-only* git repositories into a selected project's source directory.  The help message for the `spack mpd git-clone` command is:

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
> 1. When using `spack mpd g <repository name>`, the cloned repository will be read-only (i.e. no pushes allowed to the remote repository).  Users who would like to clone repositories with write permissions should use the corresponding repository URL (e.g. `spack mpd g git@github.com/Org/RepoName.git`).
> 2. `spack mpd g` does not yet support forking of GitHub repositories.  If this is desired, users should use the [GitHub CLI](https://cli.github.com) directly.  A feature request could also be made of `spack-mpd`.
