from . import config
from .preconditions import State, preconditions
from .spack_compat import tty
from .util import cyan, maybe_with_color

SUBCOMMAND = "list"
ALIASES = ["ls"]


def setup_subparser(subparsers):
    subparsers.add_parser(
        SUBCOMMAND, description="list MPD projects", aliases=ALIASES, help="list MPD projects"
    )


def format_fields(name, selected):
    # Conventions
    #
    # - No color or indicator: not selected for any process
    # - Green, with "▶": selected on only the current process
    # - Cyan, with "◀": selected on other process
    # - Cyan, with "↔": selected on more than one other process
    # - Yellow, with "↔": selected on this process and at least one more other process

    indicator = " "
    color = ""
    warning = ""
    match = selected.get(name)
    if not match:
        return indicator, color, warning

    match_length = len(match)
    assert match_length > 0
    if config.session_id() in match:
        indicator = "▶"
        color = "G" if match_length == 1 else "Y"
    else:
        indicator = "◀"
        color = "c"

    warning = "Warning: used by more than one shell" if match_length > 1 else ""

    return indicator, color, warning


def _no_known_projects():
    tty.msg("No existing MPD projects")


def list_projects():
    cfg = config.mpd_config()
    if not cfg:
        _no_known_projects()
        return

    projects = cfg.get("projects")
    if not projects:
        _no_known_projects()
        return

    msg = "Existing MPD projects:\n\n"
    name = "Project name"
    name_width = max(len(k) for k in projects.keys())
    name_width = max(len(name), name_width)
    location = "Sources directory"
    groups = config.shared_source_groups(projects)
    canonical_sources = {
        name: str(config.canonical_path(value["source"])) for name, value in projects.items()
    }
    location_width = max(len(value) for value in canonical_sources.values())
    location_width = max(len(location), location_width)
    notes = "Notes"
    msg += f"   {name:<{name_width}}    {location:<{location_width}}    {notes}\n"
    msg += "   " + "-" * name_width + "    " + "-" * location_width + "    " + "-" * len(notes)

    selected = config.selected_projects()
    for key, value in sorted(projects.items()):
        indicator, color_code, warning = format_fields(key, selected)
        source = canonical_sources[key]
        peers = [peer for peer in groups.get(source, ()) if peer != key]
        notes = [note for note in (warning, f"Shared source with: {', '.join(peers)}" if peers else "") if note]
        msg += maybe_with_color(
            color_code,
            f"\n {indicator} {key:<{name_width}}    {source:<{location_width}}    {'; '.join(notes)}",
        )
    msg += f"\n\nType {cyan('spack mpd info <project name>')} for more details about a project.\n"
    print()
    tty.msg(msg)
    conflicts = config.layout_conflicts(projects)
    if conflicts:
        tty.warn(config.format_conflicts(conflicts))


def process(args):
    preconditions(State.INITIALIZED)
    list_projects()
