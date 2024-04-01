# Zapping a project

Sometimes it is helpful to remove everything from your MPD projects
build and installation directories.  This is achieved by using the
`spack mpd zap` command on a selected MPD project:

```console
$ spack mpd z -h
usage: spack mpd zap [-h] [--all | --build | --install]

delete everything in your build and/or install areas.

If no optional argument is provided, the '--build' option is assumed.

optional arguments:
  --all       delete everything in your build and install directories
  --build     delete everything in your build directory
  --install   delete everything in your install directory
  -h, --help  show this help message and exit
```
