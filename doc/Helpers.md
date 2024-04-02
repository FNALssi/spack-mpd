# Helper commands

## Listing available projects

## Cloning repositories to develop

MPD supports cloning git repositories for a selected project.  The help message for the `spack mpd git-clone` command is:

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
