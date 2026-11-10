"""Stage-1 fixture shape for `dossier` (see the stage 1 fixture format), and the model's
fixed vocabulary: the six fields and the headcount ranges."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
# The providers, in their stated order, and the methods they answer, are the mock web's.
from mockweb.admin import METHODS, PROVIDERS  # noqa: E402,F401  pylint: disable=wrong-import-position,import-error

BUILD_SECONDS = 10
# How long a check waits for a build when its subject is not the build time bound (§8): that
# bound, plus room for a client that retries failing calls. nimble-python's default retries
# (two, with backoff) take 1.2-1.5 s per failing Nimble call; 20 s covers about 13 of them.
SETTLE_SECONDS = BUILD_SECONDS + 20

NOW = "2026-03-01T09:00:00+00:00"
# Stage 3 clock: the plain companies change between MIDDLE and LATER.
MIDDLE = "2026-03-02T09:00:00+00:00"
LATER = "2026-05-01T09:00:00+00:00"

ALICE = {"id": "u_alice", "email": "alice@example.com", "password": "correct horse",
         "display_name": "Alice"}
BOB = {"id": "u_bob", "email": "bob@example.com", "password": "correct horse",
       "display_name": "Bob"}

FIELDS = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
STRING_FIELDS = ("legal_name", "hq_city", "ceo")
# Stage 3 adds `executives` (members `{"title", "name"}`), stage 4 `investors` (sorted names).
LIST_FIELDS = ("executives", "investors")
TITLES = ("cfo", "coo", "cto")
RANGES = ("1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000",
          "10001+")


def fields(stage: int) -> tuple:
    """The field names a stage-`stage` dossier must carry, in response order."""
    return FIELDS + LIST_FIELDS[:max(0, min(stage, 4) - 2)]


def assert_field_set(carried: dict, stage: int) -> None:
    """A stage-`stage` check's dossier carries its stage's fields and no field beyond stage 4's:
    a later-stage service passes an earlier stage's checks with its later fields."""
    assert set(fields(stage)) <= set(carried) <= set(fields(4)), sorted(carried)


def matches(value, expected) -> bool:
    """Whether a served field value is one the key accepts: a scalar is one of the allowed
    values; a list field's array (or null) equals the one expected array."""
    try:
        return value in expected
    except TypeError:  # an unhashable value, such as an array served for a scalar field
        return False


def fixture() -> dict:
    """The reset body: the clock and two analysts."""
    return {"now": NOW, "users": [ALICE, BOB]}


def instant(stamp: str) -> datetime:
    """An RFC 3339 timestamp with an explicit offset, as an aware datetime."""
    parsed = datetime.fromisoformat(stamp)
    assert parsed.tzinfo is not None, f"timestamp without an offset: {stamp!r}"
    return parsed


def assert_field(name: str, field: dict, stage: int = 1) -> None:
    """One field has the §4 shape: status follows value, citations follow status.

    `stage` is the service's stage; from stage 2 a field with a value may be `contested`.
    """
    assert set(field) >= {"value", "status", "citations"}, (name, field)
    if field["value"] is None:
        assert field["status"] == "unknown" and field["citations"] == [], (name, field)
        return
    assert field["status"] in (("known",) if stage < 2 else ("known", "contested")), \
        (name, field)
    assert field["citations"], f"{name} is known but cites nothing: {field}"
    for cite in field["citations"]:
        assert cite["provider"] in PROVIDERS, (name, cite)
        assert isinstance(cite["url"], str) and cite["url"], (name, cite)
        assert isinstance(cite["excerpt"], str) and 1 <= len(cite["excerpt"]) <= 500, \
            (name, cite)
    value = field["value"]
    if name == "executives":
        assert isinstance(value, list) and value and all(
            isinstance(m, dict) and set(m) == {"title", "name"} and m["title"] in TITLES
            and isinstance(m["name"], str) and m["name"] for m in value), (name, value)
    elif name == "investors":
        assert isinstance(value, list) and value and all(
            isinstance(m, str) and m for m in value), (name, value)
    elif name in STRING_FIELDS:
        assert isinstance(value, str) and value == value.strip() and value, (name, value)
    elif name == "headcount_range":
        assert value in RANGES, (name, value)
    else:
        assert isinstance(value, int) and not isinstance(value, bool), (name, value)


def assert_dossier(body: dict, stage: int = 1, fields_stage: int | None = None) -> None:
    """A dossier body has the fields of `fields_stage` (default `stage`) and none beyond stage
    4's, each of the §4 shape for the service's `stage`."""
    assert_field_set(body["fields"], stage if fields_stage is None else fields_stage)
    for name, field in body["fields"].items():
        assert_field(name, field, stage)


def assert_all_unknown(body: dict, stage: int = 1) -> None:
    """Every field is `unknown`, with no value and no citation."""
    assert_field_set(body["fields"], stage)
    for name, field in body["fields"].items():
        assert (field["value"], field["status"], field["citations"]) == (None, "unknown", []), \
            (name, field)


def assert_list_entry(entry: dict, body: dict) -> None:
    """A `GET /dossiers` entry agrees with the dossier body it lists."""
    assert entry["dossier_id"] == body["dossier_id"] and entry["domain"] == body["domain"]
    assert entry["state"] == body["state"] and entry["spent_units"] == body["spent_units"]
    assert entry["legal_name"] == body["fields"]["legal_name"]["value"]
    if body["researched_at"] is None:
        assert entry["researched_at"] is None
    else:
        assert instant(entry["researched_at"]) == instant(body["researched_at"])


# ---- stage 2: candidates and the selection rule --------------------------

KINDS = ("own", "filing", "news", "aggregator")
AUTHORITY = {"own": 2, "filing": 2, "news": 1, "aggregator": 0, None: 0}
CANDIDATE_KEYS = {"value", "url", "excerpt", "provider", "kind", "published_at",
                  "retrieved_at", "selected"}


def same_value(one, other) -> bool:
    """Stage 2: equal as JSON values, strings compared after removing surrounding whitespace."""
    if isinstance(one, str) and isinstance(other, str):
        return one.strip() == other.strip()
    return one == other and type(one) is type(other)


def rank_key(candidate: dict) -> tuple:
    """The stage-2 selection rule as a sort key, highest-ranked first: authority, later
    `published_at` (none last), smaller `url` by code point, provider order, then smaller
    value (integers by number, strings by code point)."""
    when = candidate["published_at"]
    stamp = instant(when).timestamp() if when else 0.0
    value = candidate["value"]
    return (-AUTHORITY[candidate["kind"]], when is None, -stamp, candidate["url"],
            PROVIDERS.index(candidate["provider"]),
            (isinstance(value, str), value.strip() if isinstance(value, str) else value))


def assert_candidates(name: str, field: dict, imported: bool = False) -> None:
    """A stage-2 field: well-formed candidates, the first one alone selected, and the value,
    status and citations that follow from them. Imported candidates may have a null `kind`."""
    candidates = field["candidates"]
    if not candidates:
        assert (field["value"], field["status"], field["citations"]) == (None, "unknown", []), \
            (name, field)
        return
    for cand in candidates:
        assert set(cand) >= CANDIDATE_KEYS, (name, cand)
        assert cand["provider"] in PROVIDERS, (name, cand)
        assert cand["kind"] in KINDS or (imported and cand["kind"] is None), (name, cand)
        assert isinstance(cand["url"], str) and cand["url"], (name, cand)
        assert isinstance(cand["excerpt"], str) and 1 <= len(cand["excerpt"]) <= 500, \
            (name, cand)
        if cand["published_at"] is not None:
            instant(cand["published_at"])
        instant(cand["retrieved_at"])
    assert [c["selected"] for c in candidates] == [True] + [False] * (len(candidates) - 1), \
        (name, candidates)
    value = candidates[0]["value"]
    assert same_value(field["value"], value), (name, field["value"], candidates[0])
    distinct = {json.dumps(c["value"].strip() if isinstance(c["value"], str) else c["value"])
                for c in candidates}
    assert field["status"] == ("known" if len(distinct) == 1 else "contested"), (name, field)
    assert [citation(c) for c in field["citations"]] == [
        citation(c) for c in candidates if same_value(c["value"], value)], (name, field)


def citation(item: dict) -> dict:
    """The `url`, `excerpt` and `provider` of a citation or candidate."""
    return {key: item[key] for key in ("url", "excerpt", "provider")}


# ---- stage 3: history and feed ------------------------------------------

def entry_type(old, new) -> str:
    """The type of the history entry for a selected value going from `old` to `new`, each a
    (value, true_from) pair: `correction` when both values are set and the new `true_from`
    is on or before the old one, else `change`."""
    if None in (old[0], new[0], old[1], new[1]):
        return "change"
    return "correction" if new[1] <= old[1] else "change"


def assert_entry(entry: dict, kind: str, field: dict, true_from, learned_at: str) -> None:
    """A history entry of type `kind` records `field`'s selected value, with its citations in
    any order."""
    assert entry["type"] == kind, (kind, entry)
    assert same_value(entry["value"], field["value"]), (entry, field["value"])
    assert entry["true_from"] == true_from, (true_from, entry)
    assert instant(entry["learned_at"]) == instant(learned_at), (learned_at, entry)
    assert sorted(json.dumps(citation(c), sort_keys=True) for c in entry["citations"]) == \
        sorted(json.dumps(citation(c), sort_keys=True) for c in field["citations"]), entry


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def assert_feed_entry(entry: dict, domain: str, name: str, kind: str, values: tuple,
                      true_from, learned_at: str) -> None:
    """A feed entry for one field of one build."""
    assert (entry["domain"], entry["field"]) == (domain, name), entry
    assert entry.get("type") == kind, (kind, entry)
    assert same_value(entry["from"], values[0]) and same_value(entry["to"], values[1]), \
        (values, entry)
    assert entry["true_from"] == true_from, (true_from, entry)
    assert instant(entry["learned_at"]) == instant(learned_at), (learned_at, entry)


# ---- stage 4: origins and corroboration ---------------------------------

def members(name: str, field: dict) -> list[list]:
    """The candidates of each member of a field's value: per title and name for `executives`,
    per name for `investors`, the selected value's for a field of one value; none when
    `unknown`."""
    value, cands = field["value"], field["candidates"]
    if value is None:
        return []
    if name == "executives":
        return [[c for c in cands if (c.get("title"), c["value"]) == (m["title"], m["name"])]
                for m in value]
    if name == "investors":
        return [[c for c in cands if c["value"] == member] for member in value]
    return [[c for c in cands if same_value(c["value"], value)]]


def assert_origins(name: str, field: dict) -> None:
    """A stage-4 field: every candidate has an `origin`; `origins` lists the distinct origins
    of the candidates of its members, sorted, `[]` when `unknown`; and `corroborated` is true
    exactly when every member's candidates have two or more."""
    for cand in field["candidates"]:
        assert isinstance(cand.get("origin"), str) and cand["origin"], (name, cand)
    groups = members(name, field)
    wanted = sorted({c["origin"] for group in groups for c in group})
    assert field["origins"] == wanted, (name, field["origins"], wanted)
    assert field["corroborated"] is (bool(groups) and all(
        len({c["origin"] for c in group}) >= 2 for group in groups)), (name, field)


def assert_batch(body: dict, domains: list, budget_units: int) -> None:
    """A batch body has the stage-4 shape: its dossiers in the order given, `running` exactly
    while one of them builds, and spending within its budget."""
    assert set(body) >= {"batch_id", "state", "budget_units", "spent_units", "dossiers"}, body
    assert [d["domain"] for d in body["dossiers"]] == list(domains), body
    assert all(d["state"] in ("building", "ready", "failed") for d in body["dossiers"]), body
    building = any(d["state"] == "building" for d in body["dossiers"])
    assert body["state"] == ("running" if building else "done"), body
    assert body["budget_units"] == budget_units, body
    assert isinstance(body["spent_units"], int) and 0 <= body["spent_units"] <= budget_units, body
