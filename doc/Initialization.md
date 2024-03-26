# Initialization (once per system)

You must initialize MPD on the system where you intend to use it.
This needs to be done only once per system and is achieved by typing:

```console
$ spack mpd init
```

A successful initialization will print something like:

``` console
==> Using Spack instance at /scratch/knoepfel/spack
==> Added repo with namespace 'local-mpd'.
```

At this point, you may safely use any MPD subcommand.

### Reinitialization

Reinitialization of MPD on a given system is not yet natively
supported.  If you execute `spack mpd init` again on a system that you
have already initialized, you will see something like:

``` console
==> Using Spack instance at /scratch/knoepfel/spack
==> Warning: MPD already initialized on this system (/home/knoepfel/.mpd)
```

If you wish to "start from scratch" you may remove the directory that
is reported above (e.g. `/home/knoepfel/.mpd`), but you must
additionally invoke `spack repo rm local-mpd`.  It is also recommended
that _before_ you remove the above directory, you uninstall any
packages or environments whose recipe files or environment
specifications are located in the that directory.

### A writeable Spack instance

If you do not have write access to the Spack instance you are using,
when invoking `spack mpd init` you will see an error like:

```console
==> Using Spack instance at /scratch/knoepfel/spack

==> Error: To use MPD, you must have a Spack instance you can write to.
           You do not have permission to write to the Spack instance above.
           Please contact scisoft-team@fnal.gov for guidance.
```

At this point, MPD does not yet support the creation of writeable
Spack instances as part of the initialization process, but we expect
this limitation to be addressed soon.
