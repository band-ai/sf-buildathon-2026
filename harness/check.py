"""Everything about a submission repository a judge can check without Docker.

`harness run --repo` covers gate 3 by building the service. This covers the rest:
layout, mandates, the room log, and the two things that must not be in a public
repository -- credentials, and the problem's answer written into a mandate.
"""
from __future__ import annotations

import json
import pathlib
import re
import shlex
import sys
from datetime import datetime

from harness import vocabulary
from harness.challenges import available

# Credential shapes that must not reach a public repository. Short on purpose.
SECRETS: tuple[tuple[str, str], ...] = (
    # A token, not the word after "bearer": 20+ characters with a digit in them.
    # `bearer authentication` in a comment is prose, and `check` fails a submission.
    ("bearer-token", r"(?i)\bbearer\s+(?=[A-Za-z0-9._\-]*\d)[A-Za-z0-9._\-]{20,}"),
    ("api-key", r"\bsk-[A-Za-z0-9._\-]{16,}"),
    ("aws-access-key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("github-token", r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    ("env-assignment", r"(?i)\b[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)\s*=\s*\S+"),
    # No quote or backslash in the user or password: in code, they end the URL.
    ("url-credentials", r"""(?<=://)[^/\s:@"'\\]+:[^/\s@"'\\]+(?=@)"""),
)
# The room as downloaded from Band, saved unchanged at the repository root.
ROOM = "room.json"
DOWNLOAD = ("open the room in the Band console (Band Desktop: the room's ⋮ menu, Open in "
            "Band), choose ⋮, Download, Download full session, and save the file "
            "unchanged as room.json at the repository root")
# Or one download per stage, for a band that moved to a fresh room each stage.
STAGE_ROOM = re.compile(r"^room-([1-4])\.json$")
# Keys every Band full-session download writes. Band may add keys; it never drops these.
EXPORT_KEYS = ("exportedAt", "filters", "messages", "room", "scope")
MESSAGE_KEYS = ("content", "id", "insertedAt", "messageType", "metadata", "senderId",
                "senderName", "senderType", "threadId")
SENDER_TYPES = ("Agent", "User")
# Each mandate says what the seat runs, so a judge can read the factory without Band.
SEAT_FIELDS = ("Harness", "Model")

REQUIRED_FILES = ("README.md", "FACTORY.md")
# A Dossier entry submits its highest completed stage's `GET /dossiers/runway.com`
# response, built against the live web; it is evidence, not scored.
LIVE_DOSSIER = {"dossier": ("dossier-runway.com.json", "runway.com")}
DOSSIER_FIELDS = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range",
                  "funding_total")
DOSSIER_LATER_FIELDS = ("executives", "investors")
STAGE_FOLDER = re.compile(r"^stage-[1-4]$")
TEXT_SUFFIXES = {".md", ".py", ".txt", ".json", ".jsonl", ".yml", ".yaml", ".toml",
                 ".env", ".cfg", ".ini", ".js", ".ts", ".sh", ".go", ".rb", ".rs", ".java"}
# A suffix is not how these two are recognised, and they are where a key actually lands.
TEXT_NAMES = {"Dockerfile", ".env", ".envrc", "Makefile"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "target", "dist"}
# `NAME=value` is a guess, and in source it guesses wrong: `password = body["password"]`
# and `token = uuid4().hex` are every auth endpoint ever written, including this event's
# own scaffold. Keep it for config, where a bare assignment really is a credential.
CONFIG_ONLY = {"env-assignment"}
CONFIG_SUFFIXES = {".env", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".json"}


def check_repo(path: pathlib.Path | str, track: str) -> list[str]:
    """Every problem found, in the order a team would fix them. Empty means good."""
    root = pathlib.Path(path)
    if not root.is_dir():
        return [f"{root} is not a directory"]
    return (_layout(root, track) + _live_dossier(root, track) + _mandates(root, track)
            + _room(root) + _seats_have_mandates(root) + _credentials(root))


def warnings(path: pathlib.Path | str, track: str) -> list[str]:
    """What a team should look at although it fails no gate: a live dossier that is mostly
    unknown, which a service that stops waiting for the live providers produces."""
    root = pathlib.Path(path)
    if track not in LIVE_DOSSIER or _live_dossier(root, track):
        return []
    name = LIVE_DOSSIER[track][0]
    fields = json.loads((root / name).read_text(encoding="utf-8"))["fields"]
    unknown = sum(fields[field]["value"] is None for field in DOSSIER_FIELDS)
    if unknown * 2 <= len(DOSSIER_FIELDS):
        return []
    return [f"{name} has {unknown} of its {len(DOSSIER_FIELDS)} fields unknown. The live "
            f"providers answer far more slowly than the sample ones: a search can take over "
            f"ten seconds and a research run about a minute, and a service that stops "
            f"waiting sooner leaves fields unknown. This fails no gate"]


def _live_dossier(root: pathlib.Path, track: str) -> list[str]:
    """The track's live dossier, when it asks for one: the verbatim dossier response."""
    if track not in LIVE_DOSSIER:
        return []
    name, domain = LIVE_DOSSIER[track]
    path = root / name
    if not path.is_file():
        return [f"{name} is missing; it is the GET /dossiers/{domain} response from your "
                f"highest completed stage, built against the live web"]
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"{name} is not JSON: {exc}"]
    fields = body.get("fields") if isinstance(body, dict) else None
    allowed_sets = [set(DOSSIER_FIELDS + DOSSIER_LATER_FIELDS[:n]) for n in range(3)]
    if not isinstance(fields, dict) or body.get("domain") != domain \
            or set(fields) not in allowed_sets:
        return [f"{name} is not the GET /dossiers/{domain} response: it needs domain "
                f'"{domain}" and the six fields, optionally executives, then investors']
    if body.get("state") != "ready" or not _live_timestamp(body.get("researched_at")) \
            or not isinstance(body.get("dossier_id"), str) or not 1 <= len(body["dossier_id"]) <= 64 \
            or type(body.get("spent_units")) is not int or body["spent_units"] < 0:
        return [f"{name} needs a ready dossier with dossier_id, researched_at and spent_units"]
    for field, value in fields.items():
        if not _live_field(field, value):
            return [f"{name} has an invalid {field} field: check value, status and citations"]
    return []


def _live_timestamp(value) -> bool:
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _live_field(name, field) -> bool:
    """Structural evidence only: this cannot verify live provenance or stage completion."""
    if not isinstance(field, dict) or not {"value", "status", "citations"} <= field.keys():
        return False
    value, status, citations = field["value"], field["status"], field["citations"]
    if not isinstance(citations, list):
        return False
    if value is None:
        return status == "unknown" and citations == []
    if status not in ("known", "contested") or not citations:
        return False
    for cite in citations:
        if not isinstance(cite, dict) or cite.get("provider") not in (
                "nimble", "tavily", "kernel", "browserbase") or not all(
                    isinstance(cite.get(k), str) and cite[k].strip() for k in ("url", "excerpt")):
            return False
    if name in ("founded_year", "funding_total"):
        return type(value) is int and value >= 0
    if name == "headcount_range":
        return value in ("1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000",
                         "5001-10000", "10001+")
    if name == "executives":
        if not isinstance(value, list) or not value:
            return False
        titles = []
        for member in value:
            if not isinstance(member, dict) or member.get("title") not in ("cfo", "coo", "cto") \
                    or not isinstance(member.get("name"), str) or not member["name"].strip():
                return False
            titles.append(member["title"])
        return titles == [t for t in ("cfo", "coo", "cto") if t in titles]
    if name == "investors":
        return status == "known" and isinstance(value, list) and bool(value) and all(
            isinstance(v, str) and v.strip() for v in value) and value == sorted(set(value))
    return isinstance(value, str) and bool(value.strip())


def _layout(root: pathlib.Path, track: str) -> list[str]:
    from harness.cli import available_stages  # pylint: disable=import-outside-toplevel
    problems = []
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            problems.append(f"{name} is missing; it is where the factory is described")
    if not (root / "stage-1").is_dir():
        problems.append("stage-1/ is missing; every entry needs one complete stage 1")
    defined = available_stages(track)
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name in SKIP_DIRS:
            continue
        if re.match(r"^stage[-_]", child.name) and not STAGE_FOLDER.match(child.name):
            problems.append(f"{child.name}/ is not a stage folder the harness will "
                            f"find; name it stage-1 through stage-4")
            continue
        if not STAGE_FOLDER.match(child.name):
            continue
        stage = child.name.removeprefix("stage-")
        if stage not in defined:
            problems.append(f"{child.name}/ is present, but {track} defines stages "
                            f"{', '.join(defined)}")
            continue
        # A stage folder copied forward brings the `.git` of whatever it was copied
        # from, and git then records a gitlink instead of the files. Every file below
        # is present on disk and absent from a clone, so this is the one defect the
        # directory you worked in cannot show you.
        if (child / ".git").exists():
            problems.append(f"{child.name}/ is a git repository of its own, so a clone "
                            f"of this submission gets an empty {child.name}/. Delete "
                            f"{child.name}/.git and commit the files themselves")
        # Only stage-1 is a gate. A later folder without these simply does not build,
        # so it claims nothing and caps the chain, as an absent folder would.
        for required in ("Dockerfile", "RUN.md") if stage == "1" else ():
            if not (child / required).is_file():
                problems.append(f"stage-1/{required} is missing; gate 3 builds stage-1 "
                                f"from its Dockerfile by following its RUN.md")
    return problems


def _mandates(root: pathlib.Path, track: str) -> list[str]:
    folder = root / "mandates"
    if not folder.is_dir():
        return ["gate 1: mandates/ is missing; every seat needs a mandate file"]
    files = sorted(folder.glob("*.md"))
    problems = []
    if len(files) < 3:
        problems.append(f"gate 1: {len(files)} mandate file(s) in mandates/; three or "
                        f"more distinct seats are required")
    for mandate in files:
        text = mandate.read_text(errors="replace")
        for field in SEAT_FIELDS:
            if not re.search(rf"(?im)^[-*_ \t]*{field}[*_ \t]*:[*_ \t]*[^*_\s]", text):
                problems.append(f"gate 1: mandates/{mandate.name} has no `{field}:` line; "
                                f"say which {field.lower()} this seat runs")
    # The same tokens and the same list the organizers audit against after submissions
    # close, reported with a line number so a team can fix the line rather than hunt
    # for it. A substring scan would flag `table_ids` inside `available_table_ids`
    # twice and match it inside an unrelated word.
    distinctive = set(vocabulary.for_track(track))
    for mandate in files:
        seen = set()
        for number, line in enumerate(
                mandate.read_text(errors="replace").splitlines(), 1):
            for kind, term in vocabulary.terms_in(line):
                if term in distinctive and (number, term) not in seen:
                    seen.add((number, term))
                    problems.append(
                        f"gate 4: mandates/{mandate.name}:{number} names the {track} "
                        f"problem with the {kind} `{term}`, rather than how your factory "
                        f"works. Move track-specific detail into the task you give the "
                        f"band in the room")
    return problems


def room_files(root: pathlib.Path | str) -> list[pathlib.Path]:
    """`room.json`, else the per-stage downloads in stage order."""
    root = pathlib.Path(root)
    if (root / ROOM).is_file():
        return [root / ROOM]
    return sorted(p for p in root.glob("room-*.json") if STAGE_ROOM.match(p.name))


def load_room(root: pathlib.Path | str) -> tuple[dict, list]:
    """({seat id: display name}, messages) from `room.json` or the per-stage downloads,
    merged. A seat keeps its Band id from room to room, so the merge is by id.

    Raises OSError when there is none and ValueError on anything the Band download
    would not produce, which callers turn into a readable problem.
    """
    files = room_files(root)
    if not files:
        raise FileNotFoundError(f"{ROOM} is missing")
    seats, messages = {}, []
    for path in files:
        more_seats, more = parse_room(json.loads(path.read_text()))
        seats.update(more_seats)
        messages += more
    return seats, messages


def parse_room(room) -> tuple[dict, list]:
    """({seat id: display name}, messages) from one parsed Band room download."""
    messages = room.get("messages") if isinstance(room, dict) else None
    if not isinstance(messages, list) or not all(isinstance(m, dict) for m in messages):
        raise ValueError("expected an object whose `messages` is a list of message objects")
    seats = {m["senderId"]: m.get("senderName") or m["senderId"] for m in messages
             if m.get("senderId") and str(m.get("senderType", "")).lower() == "agent"}
    return seats, messages


def said(messages: list) -> list:
    """Only what a seat said: a mention echoed in a tool call or its output is not one
    seat addressing another."""
    return [m for m in messages if str(m.get("senderType", "")).lower() == "agent"
            and m.get("messageType") == "text"]


def _room(root: pathlib.Path) -> list[str]:
    files = room_files(root)
    if not files:
        return [f"{ROOM} is missing; {DOWNLOAD}"]
    problems = []
    if files[0].name == ROOM:
        if any(STAGE_ROOM.match(p.name) for p in root.iterdir()):
            problems.append(f"{ROOM} and room-N.json are both present; commit the one room "
                            f"as {ROOM}, or one download per stage as room-N.json")
    else:
        # A stage without its room would hide how that stage was steered.
        for folder in sorted(root.glob("stage-[1-4]")):
            stage_room = f"room-{folder.name[-1]}.json"
            if folder.is_dir() and not (root / stage_room).is_file():
                problems.append(f"{folder.name}/ has no {stage_room}; with one room per "
                                f"stage, download each stage's room the same way and save "
                                f"it as room-<stage>.json")
    for path in files:
        try:
            room = json.loads(path.read_text())
            parse_room(room)
        except (ValueError, OSError) as exc:
            return problems + [f"{path.name} could not be read ({exc}); {DOWNLOAD}"]
        shape = _not_a_download(room, room["messages"])
        if shape:
            problems.append(f"gate 2: {path.name} is not an unchanged Band download "
                            f"({shape}); {DOWNLOAD}")
        if room.get("scope", "full") != "full":
            problems.append(f"{path.name} is a filtered download (scope "
                            f"`{room.get('scope')}`); use Download full session, not "
                            f"Download filtered")
    seats, messages = load_room(root)
    if len(seats) < 3:
        problems.append(f"gate 1: the room holds {len(seats)} agent seat(s); three or "
                        f"more distinct seats are required")
    edges = {(m["senderId"], target) for m in said(messages) for target in seats
             if target != m.get("senderId") and mentions(m.get("content"), target)}
    if not any((b, a) in edges for a, b in edges):
        problems.append("gate 2: two of your own seats must exchange messages using "
                        "each other's @handles, with a reply in each direction")
    return problems


def _not_a_download(room: dict, messages: list) -> str:
    """What a hand-written or edited room lacks that every Band export has, else ""."""
    missing = [key for key in EXPORT_KEYS if key not in room]
    missing += sorted({key for m in messages for key in MESSAGE_KEYS if key not in m})
    found = [f"missing `{key}`" for key in missing]
    senders = sorted({str(m.get("senderType")) for m in messages} - set(SENDER_TYPES))
    found += [f"senderType `{sender}`" for sender in senders]
    return "; ".join(found)


def mentions(content, seat_id: str) -> bool:
    """Whether `content` addresses that seat. Band stores a typed `@handle` as
    `@[[participant-id]]`, and that is the only form the download carries."""
    return f"@[[{seat_id}]]" in str(content or "")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _seats_have_mandates(root: pathlib.Path) -> list[str]:
    """Gate 1 is a mandate per seat, so a filename has to name a seat that exists.

    Counting three files and three seats separately passes a repository with three
    mandates for seats nobody configured.
    """
    if not (root / "mandates").is_dir():
        return []                      # `_mandates` already reported it; do not repeat
    try:
        seats, _messages = load_room(root)
    except (OSError, ValueError):
        return []                      # `_room` already reported it; do not repeat
    files = {_slug(p.stem) for p in (root / "mandates").glob("*.md")}
    missing = sorted(name for name in set(seats.values()) if _slug(name) not in files)
    if missing:
        return [f"gate 1: no mandate file for {', '.join(missing)}; name each one after "
                f"the seat it belongs to, e.g. mandates/{_slug(missing[0]) or 'seat'}.md"]
    return []


def _credentials(root: pathlib.Path) -> list[str]:
    """Name the file and the shape, never the secret: this output ends up in logs."""
    problems = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if (not path.is_file() or SKIP_DIRS & set(relative.parts)
                or (path.suffix.lower() not in TEXT_SUFFIXES
                    and path.name not in TEXT_NAMES)):
            continue
        # The room download is JSON, but its tool results are source code, where the
        # `NAME=value` guess is wrong for the same reason it is in a .py file.
        config = ((path.suffix.lower() in CONFIG_SUFFIXES or path.name in TEXT_NAMES)
                  and str(relative) != ROOM and not STAGE_ROOM.match(str(relative)))
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for name, pattern in SECRETS:
            if name in CONFIG_ONLY and not config:
                continue
            if re.search(pattern, text):
                article = "an" if name[0] in "aeiou" else "a"
                problems.append(
                    f"{relative} looks like it holds {article} {name}. This repository "
                    f"is public: remove it, rotate the credential, and rewrite the "
                    f"history that carried it")
                break
    return problems


def add_parser(sub) -> None:
    """Register the check subcommand."""
    p = sub.add_parser("check", help="validate a submission repository, offline")
    p.add_argument("repo", help="the submission repository")
    p.add_argument("--track", required=True, choices=available())
    p.set_defaults(func=cmd_check)


def cmd_check(args) -> int:
    """Print every offline problem with a repository; nonzero if there are any."""
    problems = check_repo(pathlib.Path(args.repo), args.track)
    for problem in problems:
        print(problem, file=sys.stderr)
    for warning in warnings(pathlib.Path(args.repo), args.track):
        print(f"warning: {warning}", file=sys.stderr)
    print(f"{len(problems)} problem(s)" if problems else
          "ok — gates 1, 2 and the mandate part of gate 4 pass. Not checked here: gate 3 "
          "(stage-1/ builds and serves /health). Run: python -m harness run --track "
          f"{args.track} --repo {shlex.quote(args.repo)} --stage 1 --mode isolated",
          file=sys.stderr)
    return 1 if problems else 0
