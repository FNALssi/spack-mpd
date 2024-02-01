import llnl.util.tty as tty
import spack.util.git
import os.path
import pathlib


class GitHubRepo:
    def __init__(self, organization, repo):
        self._org = organization
        self._repo = repo

    def url(self):
        return f"https://github.com/{self._org}/{self._repo}.git"


class RedmineRepo:
    def __init__(self, repo):
        self._repo = repo

    def url(self):
        return f"https://cdcvs.fnal.gov/projects/{self._repo}"


class GitHubOrg:
    def __init__(self, organization):
        self._org = organization

    def repo(self, repo_name):
        return GitHubRepo(self._org, repo_name)


class Suite:
    def __init__(self, name, gh_org_name=None, repos=[]):
        self.name = name
        self.org_name = gh_org_name
        self.org = GitHubOrg(self.org_name) if gh_org_name else None
        self.repos = repos

    def repositories(self):
        if self.org:
            return {p: self.org.repo(p) for p in self.repos}
        else:
            # If not GitHub, it's redmine
            return {p: RedmineRepo(p) for p in self.repos}


_supported_suites = {
    Suite(
        "art",
        gh_org_name="art-framework-suite",
        repos=[
            "cetlib-except",
            "cetlib",
            "fhicl-cpp",
            "messagefacility",
            "hep_concurrency",
            "canvas",
            "art",
        ],
    ),
    Suite(
        "artdaq",
        gh_org_name="art-daq",
        repos=[
            "artdaq_core",
            "artdaq_core_demo",
            "artdaq_utilities",
            "artdaq_ganglia_plugin",
            "artdaq_epics_plugin",
            "artdaq_database",
            "artdaq_daqinterface",
            "artdaq_mpich_plugin",
            "artdaq_mfextensions",
        ],
    ),
    Suite(
        "critic",
        gh_org_name="art-framework-suite",
        repos=[
            "cetlib-except",
            "cetlib",
            "hep-concurrency",
            "fhicl-cpp",
            "fhicl-py",
            "messagefacility",
            "canvas",
            "canvas-root-io",
            "art",
            "art-root-io",
            "gallery",
            "critic",
        ],
    ),
    Suite(
        "dune",
        gh_org_name="DUNE",
        repos=[
            "dunecore",
            "duneopdet",
            "dunesim",
            "dunecalib",
            "duneprototypes",
            "dunedataprep",
            "dunereco",
            "duneana",
            "duneexamples",
            "dunesw",
            "duneutil",
            "protoduneana",
        ],
    ),
    Suite(
        "gallery",
        gh_org_name="art-framework-suite",
        repos=[
            "cetlib_except",
            "cetlib",
            "hep-concurrency",
            "fhicl-cpp",
            "fhicl-py",
            "messagefacility",
            "canvas",
            "canvas_root_io",
            "gallery",
        ],
    ),
    Suite(
        "larsoft",
        gh_org_name="LArSoft",
        repos=[
            "larcore",
            "lardata",
            "larevt",
            "larsim",
            "larsimrad",
            "larsimdnn",
            "larg4",
            "larreco",
            "larrecodnn",
            "larana",
            "larexamples",
            "lareventdisplay",
            "larpandora",
            "larfinder",
            "larwirecell",
            "larsoft",
        ],
    ),
    Suite(
        "larsoftobj",
        gh_org_name="LArSoft",
        repos=[
            "larcoreobj",
            "lardataobj",
            "larcorealg",
            "lardataalg",
            "larvecutils",
            "larsoftobj",
        ],
    ),
    Suite(
        "nu",
        gh_org_name="NuSoftHEP",
        repos=[
            "nusimdata",
            "nuevdb",
            "nug4",
            "nugen",
            "nurandom",
            "nufinder",
            "nutools",
        ],
    ),
    Suite(
        "sbn",
        gh_org_name="SBNSoftware",
        repos=[
            "sbncode",
            "sbnobj",
            "sbnanaobj",
            "sbndcode",
            "sbndutil",
            "icaruscode",
            "icarusutil",
            "icarusalg",
            "icarus_signal_processing",
            "sbnci",
        ],
    ),
    Suite(
        "sbndaq",
        gh_org_name="SBNSoftware",
        repos=[
            "sbndaq",
            "sbndaq_artdaq",
            "sbndaq_artdaq_core",
            "sbndaq_xporter",
            "sbndaq_minargon",
            "sbndaq_online",
            "sbndaq_decode",
        ],
    ),
    Suite(
        "uboone",
        repos=[
            "uboonecode",
            "ubutil",
            "uboonedata",
            "ublite",
            "ubana",
            "ubreco",
            "ubsim",
            "ubevt",
            "ubraw",
            "ubcrt",
            "ubcore",
            "ubcv",
            "ubobj",
        ],
    ),
}


def suite_for(suite_name: str) -> Suite:
    return next(filter(lambda s: s.name == suite_name, _supported_suites))


def help_suites():
    print()
    tty.msg("Supported suites:\n")
    title = "Suite"
    suite_width = max(len(s.name) for s in _supported_suites)
    print(f"  {title:<{suite_width}}  Repositories")
    print("  " + "-" * 100)
    for suite in sorted(_supported_suites, key=lambda s: s.name):
        repo_string = " ".join(suite.repos)
        print(f"  {suite.name:<{suite_width}}  {repo_string}")
    print()


def _known_art_specs():
    suite = suite_for("critic")
    known_specs = suite.repositories()
    known_specs["cetmodules"] = GitHubRepo("FNALssi", "cetmodules")
    known_specs["art-g4tk"] = suite.org.repo("art-g4tk")
    known_specs["ifdh-art"] = suite.org.repo("ifdh-art")
    return known_specs


def _known_artdaq_specs():
    return suite_for("artdaq").repositories()


def _known_nu_specs():
    suite = suite_for("nu")
    known_specs = suite.repositories()
    others = ["geant4reweight", "nusystematics", "systematicstools"]
    known_specs.update({p: suite.org.repo(p) for p in others})
    return known_specs


def _known_dune_specs():
    suite = suite_for("dune")
    known_specs = suite.repositories()
    others = ["garsoft", "garana", "duneanaobj", "dunepdlegacy", "sandreco", "webevd"]
    known_specs.update({p: suite.org.repo(p) for p in others})
    return known_specs


def _known_sbn_specs():
    suite = suite_for("sbn")
    known_specs = suite.repositories()
    others = ["sbnana", "sbndata", "sbndqm", "sbndaq_artdaq_core"]
    known_specs.update({p: suite.org.repo(p) for p in others})
    # sbncode needs special instructions:
    #   ["sbncode", { github => ["$sbn_github/sbncode", git_args => [ qw(--recurse-submodules) ]] }]
    return known_specs


def _known_sbndaq_specs():
    return suite_for("sbndaq").repositories()


def _known_larsoft_specs():
    suite = suite_for("larsoft")
    known_specs = suite.repositories()
    known_specs.update(suite_for("larsoftobj").repositories())
    others = ["larpandoracontent", "larbatch", "larutils", "larnusystematics"]
    known_specs.update({p: suite.org.repo(p) for p in others})
    return known_specs


def _known_uboone_specs():
    return suite_for("uboone").repositories()


def known_repos():
    result = {}
    result.update(_known_art_specs())
    result.update(_known_artdaq_specs())
    result.update(_known_dune_specs())
    result.update(_known_larsoft_specs())
    result.update(_known_nu_specs())
    result.update(_known_sbn_specs())
    result.update(_known_sbndaq_specs())
    result.update(_known_uboone_specs())
    return result


def help_repos():
    print()
    tty.msg("Supported repositories:\n")

    repos = known_repos()
    title = "Repository name"
    repo_width = max(len(s) for s in repos.keys())
    print(f"  {title:<{repo_width}}  URL")
    print("  " + "-" * 100)
    for name, repo in sorted(repos.items()):
        print(f"  {name:<{repo_width}}  {repo.url()}")
    print()


def clone_suite(suite_name, srcs_area, local_area):
    git = spack.util.git.git(required=True)
    git.add_default_arg("-C", srcs_area)
    suite = suite_for(suite_name)
    print()
    for name, repo in suite.repositories().items():
        local_src_dir = os.path.join(srcs_area, name)
        if os.path.exists(local_src_dir):
            tty.warn(f"{name} already cloned (skipping)")
            continue
        git("clone", repo.url())

    print()
    local_area_path = pathlib.Path(local_area)
    tty.msg(
        tty.color.colorize(
            "@*{The " + suite_name + " suite has been cloned.  You may now invoke:}"
        )
        + f"\n\n  source {local_area_path.absolute()}/finalize.sh\n"
    )
