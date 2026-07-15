import os
import os.path
import re
import select
import shutil
import subprocess
import sys
import textwrap
import urllib
from enum import Enum, auto

import spack.llnl.util.filesystem as fs
import spack.llnl.util.tty as tty
import spack.util.git
import spack.util.spack_yaml as syaml
from spack.util import executable

from .config import selected_project_config
from .preconditions import State, preconditions
from .util import bold, gray, maybe_with_color, yellow

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
        help_msg += yellow("\n(not supported on this system - requires gh, which cannot be found)")
    git.add_argument("--fork", action="store_true", help=help_msg)
    git.add_argument("--help-repos", action="store_true", help="list known repositories")
    git.add_argument(
        "--help-repos-with-urls",
        action="store_true",
        help="list known repositories with full URLs",
    )
    git.add_argument("--help-suites", action="store_true", help="list known suites")
    git.add_argument(
        "--help-suites-with-paths",
        action="store_true",
        help="list known suites and suite YAML file paths",
    )


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
    def __init__(self, name, gh_org_name=None, repos=None, suite_file=None):
        self.name = name
        self.org_name = gh_org_name
        self.org = GitHubOrg(self.org_name)
        self.repos = repos or []
        self.suite_file = suite_file

    def repositories(self):
        return {p: self.org.repo(p) for p in self.repos}


# N.B. Listing of repositories is done in alphabetical order.


def _suite_files_path():
    return os.path.join(os.path.dirname(__file__), "supported_suites")


def _load_supported_suites():
    suites = []
    suite_files_path = _suite_files_path()

    if not os.path.isdir(suite_files_path):
        tty.die(f"Suite directory does not exist: {suite_files_path}")

    for filename in sorted(os.listdir(suite_files_path)):
        if not filename.endswith("-suite.yaml"):
            continue

        suite_file = os.path.join(suite_files_path, filename)
        with open(suite_file) as f:
            loaded = syaml.load(f)

        if not isinstance(loaded, dict) or len(loaded) != 1:
            tty.die(
                "Suite definition must contain exactly one top-level suite mapping: " + suite_file
            )

        suite_name, suite_info = next(iter(loaded.items()))
        if not isinstance(suite_info, dict):
            tty.die(f"Invalid suite definition in {suite_file}: expected a mapping")

        gh_org_name = suite_info.get("gh_org_name")
        repos = suite_info.get("repos", [])
        if not isinstance(repos, list):
            tty.die(f"Invalid repos list in {suite_file}: expected a sequence")

        suite_file_display = os.path.abspath(suite_file)
        suites.append(
            Suite(suite_name, gh_org_name=gh_org_name, repos=repos, suite_file=suite_file_display)
        )

    return suites


_supported_suites = _load_supported_suites()


def suite_for(suite_name: str) -> Suite:
    return next(filter(lambda s: s.name == suite_name, _supported_suites))


def help_suites(show_suite_paths=False):
    print()
    tty.msg("Known suites:\n")
    width = shutil.get_terminal_size(fallback=(100, 24)).columns
    initial_indent = "    - "
    subsequent_indent = "      "
    for suite in sorted(_supported_suites, key=lambda s: s.name):
        suite_source = gray(f" (see {suite.suite_file})") if show_suite_paths else ""
        print(f"  {yellow(suite.name)}{suite_source}")
        if suite.repos:
            repo_text = ", ".join(suite.repos)
            print(
                textwrap.fill(
                    repo_text,
                    width=max(width, 40),
                    initial_indent=initial_indent,
                    subsequent_indent=subsequent_indent,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
        else:
            print("    (no repositories listed)")
        print()
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
    others = ["garsoft", "garana", "sandreco", "webevd"]
    known_specs.update({p: suite.org.repo(p) for p in others})
    return known_specs


def _known_sbn_specs():
    suite = suite_for("sbn")
    known_specs = suite.repositories()
    others = ["sbndata", "sbndqm"]
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


def _repo_location(repo, with_urls=False):
    url = repo.url()
    if with_urls:
        return url

    github_prefix = "https://github.com/"
    git_suffix = ".git"
    if url.startswith(github_prefix) and url.endswith(git_suffix):
        return url[len(github_prefix) : -len(git_suffix)]

    return url


def _repo_organization(repo):
    path = urllib.parse.urlparse(repo.url()).path.strip("/")
    if not path:
        return None
    return path.split("/", 1)[0]


def help_repos(with_urls=False):
    print()
    repos = known_repos()
    orgs = {_repo_organization(repo) for repo in repos.values()}
    orgs.discard(None)  # discard any repos that don't have a GitHub organization
    tty.msg(f"Known repositories: {len(repos)} across {len(orgs)} organizations\n")

    title = "Repository name"
    location_title = "URL" if with_urls else "GitHub Organization/Repository"
    repo_width = max(len(s) for s in repos.keys())
    print(f"  {title:<{repo_width}}  {location_title}")
    print("  " + "-" * repo_width + "  " + "-" * 30)
    for name, repo in sorted(repos.items()):
        print(f"  {name:<{repo_width}}  {_repo_location(repo, with_urls=with_urls)}")
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
            if clone_repos(repos_to_clone, should_fork, config["source"], config["local"]):
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
    elif args.help_suites_with_paths:
        help_suites(show_suite_paths=True)
    elif args.help_repos:
        help_repos()
    elif args.help_repos_with_urls:
        help_repos(with_urls=True)
    else:
        print()
        tty.die(
            f"At least one option required when invoking 'spack {' '.join(sys.argv[1:])}'" "\n"
        )
