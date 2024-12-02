# Installing a project

It is possible to use standard CMake commands to install an MPD
project and its developed packages as installed Spack packages and a
named environment.  This is done simply by invoking:

```console
$ spack mpd install

==> Activating development environment (/scratch/knoepfel/test-devel/local)

==> Installing developed packages with command:

cmake --install /scratch/knoepfel/test-devel/build

==> Installing environment
[+] /usr (external glibc-2.34-hjl43avhawltutkgujn2ns3577kjowlq)
[+] /usr (external glibc-2.34-smaln5legoyu46un62ag5l6uzp6lzrpv)
[+] /usr (external openssl-3.0.7-wl62it2i7iliquqoaoqbpjz735u7ytpo)
 ⋮

==> The test environment has been installed.
```

> [!NOTE]
> In the above, `test` is the name of the Spack environment and the MPD
> project name.  As such, the installation message will follow the
> pattern:
>
> ```console
> ==> The <MPD project name> environment has been installed.
> ```

All built binaries of the developed packages are then installed as
Spack packages:

```console
$ spack -e test find -c
==> In environment test
==> 3 root specs
[+] cetlib  [+] cetlib-except  [+] hep-concurrency

==> Included specs
gcc@14
⋮
```

> [!TIP]
> The installation of an MPD project can take a little longer than
> simply invoking (e.g.) `make install` as Spack artifacts must be
> created to install the built binaries as Spack packages (usually a
> few seconds longer per package).  A verbose printout can be enabled to
> have a better sense of what is being installed:
>
> ```console
> $ spack -v mpd install
> ```

After installation, the MPD project project may serve as an
environment from which to base another MPD project:

```console
$ spack mpd new-project --name next -E test ...
```

where the project `next` is built off of the installed environment
from the MPD project `test`.
