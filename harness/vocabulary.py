"""Track-distinctive identifiers a mandate must not contain.

A mandate says how a seat works. Naming this problem's answer in it is overfitting, so
`harness check` scans every file in `mandates/` against the challenge's `vocabulary.json`
and reports the file and the line. Track-specific detail belongs in the task you give the
band in the room, not in a mandate.

Each `vocabulary.json` is **generated from the specs** by `python -m harness.mandate_audit
--emit-vocabulary`, and identical to the list the organizers audit against after
submissions close. Ordinary words the specs happen to use -- `amount`, `balance`,
`handle`, `status`, `available` -- are not in it, because banning them would fail
everyone. Error codes and fixture identifiers are, because they are this problem's answer.
"""
import json
import re

from harness.challenges import challenge_dir

# Identifier shapes only. Prose, numbers and quoted fragments are not evidence of
# anything, and a term that needs a judgement call does not belong in a scan whose
# output is a disqualification. A path starts a token: in `import/export` the slash
# joins two words.
SHAPES = (
    ("endpoint", re.compile(r"(?<![a-z0-9_])/[a-z][a-z0-9_]*(?:[/-][a-z0-9_{}]+)*")),
    ("identifier", re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")),
    ("test id", re.compile(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+\b")),
)


def terms_in(text: str):
    """(kind, term) for every identifier-shaped token in `text`, lowercased."""
    lowered = text.lower()
    for kind, pattern in SHAPES:
        for term in pattern.findall(lowered):
            yield kind, term


def for_track(track: str) -> tuple[str, ...]:
    """The track's distinctive identifiers; empty for an unknown track."""
    try:
        return tuple(json.loads((challenge_dir(track) / "vocabulary.json").read_text()))
    except FileNotFoundError:
        return ()
