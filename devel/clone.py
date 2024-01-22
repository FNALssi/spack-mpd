import llnl.util.tty as tty

_supported_suites = {
    "art": "cetlib-except cetlib fhicl-cpp messagefacility hep_concurrency canvas art",
    "artdaq": "artdaq_core artdaq_core_demo artdaq_utilities artdaq_ganglia_plugin artdaq_epics_plugin artdaq_database artdaq_daqinterface artdaq_mpich_plugin artdaq_mfextensions",
    "critic": "cetlib-except cetlib hep-concurrency fhicl-cpp fhicl-py messagefacility canvas canvas-root-io art art-root-io gallery critic",
    "dune": "dunecore duneopdet dunesim dunecalib duneprototypes dunedataprep dunereco duneana duneexamples dunesw duneutil protoduneana",
    "gallery": "cetlib_except cetlib hep-concurrency fhicl-cpp fhicl-py messagefacility canvas canvas_root_io gallery",
    "larsoft": "larcore lardata larevt larsim larsimrad larsimdnn larg4 larreco larrecodnn larana larexamples lareventdisplay larpandora larfinder larwirecell larsoft",
    "larsoftobj": "larcoreobj lardataobj larcorealg lardataalg larvecutils larsoftobj",
    "nu": "nusimdata nuevdb nug4 nugen nurandom nufinder nutools",
    "sbn": "sbncode sbnobj sbnanaobj sbndcode sbndutil icaruscode icarusutil icarusalg icarus_signal_processing sbnci",
    "sbndaq": "sbndaq sbndaq_artdaq sbndaq_artdaq_core sbndaq_xporter sbndaq_minargon sbndaq_online sbndaq_decode",
    "uboone": "uboonecode ubutil uboonedata ublite ubana ubreco ubsim ubevt ubraw ubcrt ubcore ubcv ubobj",
}


def help_suites():
    print()
    tty.msg("Supported suites:\n")
    title = "Suite"
    suite_width = max(len(s) for s in _supported_suites.keys())
    print(f"  {title:<{suite_width}}  Repositories")
    print("  " + "-" * 100)
    for suite, repositories in _supported_suites.items():
        print(f"  {suite:<{suite_width}}  {repositories}")
    print()


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


def _known_art_specs():
    art_gh = GitHubOrg("art-framework-suite")
    known_specs = {p: art_gh.repo(p) for p in _supported_suites["critic"].split()}
    known_specs["cetmodules"] = GitHubRepo("FNALssi", "cetmodules")
    known_specs["art-g4tk"] = art_gh.repo("art-g4tk")
    known_specs["ifdh-art"] = art_gh.repo("ifdh-art")
    return known_specs


def _known_artdaq_specs():
    artdaq_gh = GitHubOrg("art-daq")
    known_specs = {p: artdaq_gh.repo(p) for p in _supported_suites["artdaq"].split()}
    return known_specs


def _known_nu_specs():
    nu_gh = GitHubOrg("NuSoftHEP")
    known_specs = {p: nu_gh.repo(p) for p in _supported_suites["nu"].split()}
    others = ["geant4reweight", "nusystematics", "systematicstools"]
    known_specs.update({p: nu_gh.repo(p) for p in others})
    return known_specs


def _known_dune_specs():
    dune_gh = GitHubOrg("DUNE")
    known_specs = {p: dune_gh.repo(p) for p in _supported_suites["dune"].split()}
    others = ["garsoft", "garana", "duneanaobj", "dunepdlegacy", "sandreco", "webevd"]
    known_specs.update({p: dune_gh.repo(p) for p in others})
    return known_specs


def _known_sbn_specs():
    sbn_gh = GitHubOrg("SBNSoftware")
    known_specs = {p: sbn_gh.repo(p) for p in _supported_suites["sbn"].split()}
    others = ["sbnana", "sbndata", "sbndqm", "sbndaq_artdaq_core"]
    known_specs.update({p: sbn_gh.repo(p) for p in others})
    # sbncode needs special instructions:
    #   ["sbncode", { github => ["$sbn_github/sbncode", git_args => [ qw(--recurse-submodules) ]] }]
    return known_specs


def _known_sbndaq_specs():
    sbn_gh = GitHubOrg("SBNSoftware")
    known_specs = {p: sbn_gh.repo(p) for p in _supported_suites["sbndaq"].split()}
    return known_specs


def _known_larsoft_specs():
    larsoft_gh = GitHubOrg("LArSoft")
    known_specs = {p: larsoft_gh.repo(p) for p in _supported_suites["larsoft"].split()}
    known_specs.update(
        {p: larsoft_gh.repo(p) for p in _supported_suites["larsoftobj"].split()}
    )
    others = ["larpandoracontent", "larbatch", "larutils", "larnusystematics"]
    known_specs.update({p: larsoft_gh.repo(p) for p in others})
    return known_specs


def _known_uboone_specs():
    known_specs = {p: RedmineRepo(p) for p in _supported_suites["uboone"].split()}
    return known_specs


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
