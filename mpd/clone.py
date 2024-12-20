import os
import os.path
import re
import select
import subprocess
import sys
import urllib
from enum import Enum, auto

import llnl.util.filesystem as fs
import llnl.util.tty as tty

import spack.util.git
from spack.util import executable

from .config import selected_project_config
from .preconditions import State, preconditions
from .util import bold, maybe_with_color

SUBCOMMAND = "git-clone"
ALIASES = ["g", "clone"]

gh = executable.which("gh")
# Stolen from https://stackoverflow.com/a/14693789/3585575
ansi_escape = re.compile(
    r"""
    \x1B  # ESC
    (?:   # 7-bit C1 Fe (except CSI)
        [@-Z\\-_]
    |     # or [ for CSI, followed by a control sequence
        \[
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    )
""",
    re.VERBOSE,
)


def setup_subparser(subparsers):
    git_parser = subparsers.add_parser(
        SUBCOMMAND,
        description="clone git repositories for development",
        aliases=ALIASES,
        help="clone git repositories",
    )
    git_parser.add_argument(
        "repos",
        metavar="<repo spec>",
        nargs="*",
        help="a specification of a repository to clone. The repo spec may either be:\n"
        + "(a) any repository name listed by the --help-repos option, or\n"
        + "(b) any URL to a Git repository.",
    )
    git_parser.add_argument(
        "--suites",
        metavar="<suite name>",
        help="clone repositories corresponding to the given suite name (multiple allowed)",
        action="extend",
        nargs="+",
    )
    git = git_parser.add_mutually_exclusive_group()
    help_msg = "fork GitHub repository or set origin to already forked repository"
    if not gh:
        help_msg += maybe_with_color(
            "y", "\n(not supported on this system - requires gh, which cannot be found)"
        )
    git.add_argument("--fork", action="store_true", help=help_msg)
    git.add_argument("--help-repos", action="store_true", help="list supported repositories")
    git.add_argument("--help-suites", action="store_true", help="list supported suites")


class CloneState(Enum):
    UNSET = auto()
    DONE = auto()
    SKIPPED = auto()
    ERROR = auto()


class RepoStatus:
    def __init__(self):
        self._cloneState = CloneState.UNSET
        self._cloneMsg = ""
        self._forkMsg = ""

    def okay(self):
        return self._cloneState in (CloneState.DONE, CloneState.SKIPPED)

    def value(self):
        return self._cloneState

    def name(self):
        return self.value().name.lower()

    def annotation(self):
        if self._forkMsg:
            msg = self._forkMsg
            if self._cloneMsg:
                msg = self._cloneMsg + ", " + msg
            return msg
        if self._cloneMsg:
            return self._cloneMsg
        return ""

    def update(self, new_state, clone_msg="", fork_msg=""):
        assert new_state != CloneState.UNSET

        # ERROR is never overwritten
        if self._cloneState == CloneState.ERROR:
            return

        if self._cloneState in (CloneState.UNSET, CloneState.SKIPPED):
            self._cloneState = new_state
            if not self._cloneMsg and clone_msg:
                self._cloneMsg = clone_msg
            if not self._forkMsg and fork_msg:
                self._forkMsg = fork_msg
            return

        assert self._cloneState == CloneState.DONE
        # Only ERROR overwrites DONE
        if new_state == CloneState.ERROR:
            self._cloneState = CloneState.ERROR

        # If we're already in DONE state, we may still need to update
        # the fork message.
        if not self._forkMsg and fork_msg:
            self._forkMsg = fork_msg


class GitHubRepo:
    def __init__(self, organization, repo):
        self._org = organization
        self._repo = repo

    def name(self):
        return self._repo

    def url(self):
        return f"https://github.com/{self._org}/{self._repo}.git"


class RedmineRepo:
    def __init__(self, repo):
        self._repo = repo

    def name(self):
        return self._repo

    def url(self):
        return f"https://cdcvs.fnal.gov/projects/{self._repo}"


class SimpleGitRepo:
    def __init__(self, url):
        path = urllib.parse.urlparse(url).path
        self._name = os.path.basename(path).replace(".git", "")
        self._url = url

    def name(self):
        return self._name

    def url(self):
        return self._url


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


# N.B. Listing of repositories is done in alphabetical order.

_supported_suites = [
    Suite(
        "art",
        gh_org_name="art-framework-suite",
        repos=[
            "art",
            "canvas",
            "cetlib",
            "cetlib-except",
            "fhicl-cpp",
            "hep-concurrency",
            "messagefacility",
        ],
    ),
    Suite(
        "artdaq",
        gh_org_name="art-daq",
        repos=[
            "artdaq_core",
            "artdaq_core_demo",
            "artdaq_daqinterface",
            "artdaq_database",
            "artdaq_epics_plugin",
            "artdaq_ganglia_plugin",
            "artdaq_mfextensions",
            "artdaq_mpich_plugin",
            "artdaq_utilities",
        ],
    ),
    Suite(
        "critic",
        gh_org_name="art-framework-suite",
        repos=[
            "art",
            "art-root-io",
            "canvas",
            "canvas-root-io",
            "cetlib",
            "cetlib-except",
            "critic",
            "fhicl-cpp",
            "fhicl-py",
            "gallery",
            "hep-concurrency",
            "messagefacility",
        ],
    ),
    Suite(
        "dune",
        gh_org_name="DUNE",
        repos=[
            "duneana",
            "dunecalib",
            "dunecore",
            "dunedataprep",
            "duneexamples",
            "duneopdet",
            "duneprototypes",
            "dunereco",
            "dunesim",
            "dunesw",
            "duneutil",
            "protoduneana",
        ],
    ),
    Suite(
        "gallery",
        gh_org_name="art-framework-suite",
        repos=[
            "canvas",
            "canvas-root-io",
            "cetlib",
            "cetlib-except",
            "fhicl-cpp",
            "fhicl-py",
            "gallery",
            "hep-concurrency",
            "messagefacility",
        ],
    ),
    Suite(
        "larsoft",
        gh_org_name="LArSoft",
        repos=[
            "larana",
            "larcore",
            "lardata",
            "lareventdisplay",
            "larevt",
            "larexamples",
            "larfinder",
            "larg4",
            "larpandora",
            "larreco",
            "larrecodnn",
            "larsim",
            "larsimdnn",
            "larsimrad",
            "larsoft",
            "larwirecell",
        ],
    ),
    Suite(
        "larsoftobj",
        gh_org_name="LArSoft",
        repos=[
            "larcorealg",
            "larcoreobj",
            "lardataalg",
            "lardataobj",
            "larsoftobj",
            "larvecutils",
        ],
    ),
    Suite(
        "nu",
        gh_org_name="NuSoftHEP",
        repos=["nuevdb", "nufinder", "nug4", "nugen", "nurandom", "nusimdata", "nutools"],
    ),
    Suite(
        "sbn",
        gh_org_name="SBNSoftware",
        repos=[
            "icarus_signal_processing",
            "icarusalg",
            "icaruscode",
            "icarusutil",
            "sbnanaobj",
            "sbnci",
            "sbncode",
            "sbndcode",
            "sbndutil",
            "sbnobj",
        ],
    ),
    Suite(
        "sbndaq",
        gh_org_name="SBNSoftware",
        repos=[
            "sbndaq",
            "sbndaq_artdaq",
            "sbndaq_artdaq_core",
            "sbndaq_decode",
            "sbndaq_minargon",
            "sbndaq_online",
            "sbndaq_xporter",
        ],
    ),
    Suite(
        "uboone",
        repos=[
            "ubana",
            "ubcore",
            "ubcrt",
            "ubcv",
            "ubevt",
            "ublite",
            "ubobj",
            "uboonecode",
            "uboonedata",
            "ubraw",
            "ubreco",
            "ubsim",
            "ubutil",
        ],
    ),
]


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
    #  ["sbncode", { github => ["$sbn_github/sbncode", git_args => [ qw(--recurse-submodules) ]] }]
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


def _clone(repo, srcs_area):
    git = spack.util.git.git(required=True)
    git.add_default_arg("-C", srcs_area)
    local_src_dir = os.path.join(srcs_area, repo.name())
    result = git("clone", repo.url(), local_src_dir, fail_on_error=False, error=str)
    if "Cloning into" in result and git.returncode == 0:
        return None
    return result.rstrip()


def _color_from(status):
    if status.value() == CloneState.ERROR:
        return "R"
    if status.value() == CloneState.SKIPPED:
        return "y"
    if status.value() == CloneState.DONE:
        return "g"
    return None


# Stolen from https://stackoverflow.com/a/52954716/3585575
def _fork_repository():
    # The relevant message when forking is buried in a message that is
    # only printed to a TTY...so we have to fake out the system
    master_fd, tty_fd = os.openpty()
    p = subprocess.Popen(
        ["gh", "repo", "fork", "--remote"],
        bufsize=1,
        stdout=tty_fd,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )

    result = b""
    timeout = 0.04  # seconds
    while True:
        ready, _, _ = select.select([master_fd], [], [], timeout)
        if ready:
            for fd in ready:
                data = os.read(fd, 512)
                if not data:
                    break
                result += data
        elif p.poll() is not None:  # select timed-out
            break  # p exited
    for fd in (master_fd, tty_fd):
        os.close(fd)  # can't do it sooner: it leads to errno.EIO error

    p.wait()
    if p.returncode != 0:
        return "cannot fork"
    result = result.decode().strip()
    return ansi_escape.sub("", result)


def clone_repos(repos, should_fork, srcs_area, local_area):
    name_width = max(len(n) + 1 for n in repos.keys())
    name_width = max(name_width, 20)
    changed_srcs_dir = False
    for name, repo in repos.items():
        result = _clone(repo, srcs_area)
        status = RepoStatus()
        if result is None:
            status.update(CloneState.DONE, clone_msg="cloned")
            changed_srcs_dir = True
        elif "already exists" in result:
            status.update(CloneState.SKIPPED, clone_msg="already cloned")
        else:
            status.update(CloneState.ERROR, clone_msg=result)

        if status.okay() and should_fork:
            with fs.working_dir(os.path.join(srcs_area, name)):
                result = gh("repo", "set-default", repo.url(), output=str, error=str)
                if gh.returncode != 0:
                    status.update(
                        CloneState.ERROR, fork_msg="could not set default URL for forking"
                    )
                if status.okay():
                    result = _fork_repository()
                    if result == "cannot fork":
                        status.update(CloneState.ERROR, fork_msg="could not fork")
                    elif "Created fork" in result:
                        m = re.search(r"Created fork (\S+)", result, re.DOTALL)
                        status.update(CloneState.DONE, fork_msg="created fork " + m.group(1))
                    elif "already exists" in result and "Added remote" in result:
                        m = re.search(r"(\S+) already exists", result, re.DOTALL)
                        status.update(CloneState.SKIPPED, fork_msg="added fork " + m.group(1))
                    elif "already exists" in result and "Using existing remote" in result:
                        m = re.search(r"(\S+) already exists", result, re.DOTALL)
                        status.update(CloneState.SKIPPED, fork_msg="using fork " + m.group(1))
                    else:
                        status.update(CloneState.ERROR, fork_msg=result)

        line = maybe_with_color(
            _color_from(status), f"  {name + ' ':.<{name_width}}..... {status.name():<7}"
        )
        if status.annotation():
            line += f" ({status.annotation()})"
        print(line)

    return changed_srcs_dir


def process(args):
    if args.fork:
        if not gh:
            tty.die(
                f"Forking has been disabled (the {bold('gh')} executable cannot be found).\n"
                "           You can still clone repositories."
            )
        # FIXME: Should have a check for successful gh auth status command

    should_fork = args.fork and gh

    if args.repos or args.suites:
        preconditions(State.INITIALIZED, State.SELECTED_PROJECT)
        config = selected_project_config()
        changed_srcs_dir = False
        if args.repos:
            print()
            preamble = "Cloning"
            if should_fork:
                preamble += " and forking"
            tty.msg(f"{preamble}:\n")
            repos = known_repos()
            repos_to_clone = {}
            for repo_spec in args.repos:
                repo = repos.get(repo_spec, SimpleGitRepo(repo_spec))
                repos_to_clone[repo.name()] = repo
            if clone_repos(
                repos_to_clone, should_fork, config["source"], config["local"]
            ):
                changed_srcs_dir = True

        if args.suites:
            for s in args.suites:
                suite = None
                try:
                    suite = suite_for(s)
                except StopIteration:
                    print()
                    tty.warn(f"Skipping unknown suite {bold(s)}")
                    continue

                print()
                preamble = "Cloning"
                if should_fork:
                    preamble += " and forking"
                tty.msg(f"{preamble} suite {bold(s)}:\n")
                if clone_repos(
                        suite.repositories(), should_fork, config["source"], config["local"]
                ):
                    changed_srcs_dir = True

        print()
        if changed_srcs_dir:
            tty.msg("You may now invoke:\n\n  spack mpd refresh\n")
        else:
            tty.msg("No repositories added\n")
        return

    preconditions(State.INITIALIZED)

    if args.help_suites:
        help_suites()
    elif args.help_repos:
        help_repos()
    else:
        print()
        tty.die(
            f"At least one option required when invoking 'spack {' '.join(sys.argv[1:])}'" "\n"
        )
