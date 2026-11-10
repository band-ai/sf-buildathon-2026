"""The mock web's admin client, the corpus with its key, and the citation check."""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

DOSSIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DOSSIER / "web"))
# mockweb is found through the path above, as corpus_check finds it.
from mockweb import corpus as mock_corpus  # noqa: E402  pylint: disable=wrong-import-position,import-error
from mockweb.admin import METHODS, PROVIDERS  # noqa: E402  pylint: disable=wrong-import-position,import-error

KINDS = ("own", "filing", "news", "aggregator")
# The six fields of stage-1.md §4 (`fixtures.FIELDS`): the plants the checks select by default.
FIELDS = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")


class FabricationError(AssertionError):
    """A citation whose excerpt no page of the corpus carries at the cited URL."""


def collapse(text: str) -> str:
    """Text with every run of whitespace written as one space."""
    return " ".join(text.split())


def header(page) -> dict:
    """A served page's header lines (stage 1, Pages) as {name: value}."""
    lines = page.served.partition("\n\n")[0].splitlines()
    return dict(line.split(": ", 1) for line in lines if ": " in line)


def label_parts(label: str) -> tuple:
    """A plant label `kind:field@scope:epoch` as (kind, field, scope)."""
    kind, rest = label.split(":", 1)
    field, scope = rest.split("@", 1)
    return kind, field, scope.split(":")[0]


class Web:
    """The mock web's admin API."""

    def __init__(self, url: str, token: str):
        self._client = httpx.Client(base_url=url.rstrip("/"), timeout=10,
                                    headers={"X-Mock-Admin": token})

    def _post(self, path: str, body: dict) -> None:
        resp = self._client.post(path, json=body)
        assert resp.status_code == 204, f"{path} -> {resp.status_code} {resp.text[:200]!r}"

    def reset(self, epoch: int = 0) -> None:
        """Clear the call log and faults, and set the epoch."""
        self._post("/_mock/reset", {"epoch": epoch})

    def epoch(self, n: int) -> None:
        """Serve the pages of epoch `n` from now on."""
        self._post("/_mock/epoch", {"epoch": n})

    def fault(self, provider: str, methods: list[str], mode: str,
              seconds: float | None = None) -> None:
        """Make `provider` answer `methods` with `error` (500), `rate_limit` (429), 429 to
        each distinct call's first attempt (`throttle`), normally after `seconds` (`delay`),
        or as usual again (`none`)."""
        body = {"provider": provider, "methods": methods, "mode": mode}
        if seconds is not None:
            body["seconds"] = seconds
        self._post("/_mock/faults", body)

    def slow(self, seconds: float, methods: tuple = ("search",)) -> None:
        """Make every provider answer `methods` normally after `seconds`, whichever ones a
        service calls."""
        for provider in PROVIDERS:
            self.fault(provider, list(methods), "delay", seconds)

    def normal(self, methods: tuple = METHODS) -> None:
        """Make every provider answer `methods` as usual again, keeping the call log."""
        for provider in PROVIDERS:
            self.fault(provider, list(methods), "none")

    def weather(self, on: bool) -> None:
        """Turn the seeded rate limits of the corpus traits on or off."""
        self._post("/_mock/weather", {"on": on})

    def log(self) -> list[dict]:
        """Every provider call since the last reset, in order."""
        resp = self._client.get("/_mock/log")
        assert resp.status_code == 200, f"/_mock/log -> {resp.status_code} {resp.text[:200]!r}"
        return resp.json()["calls"]

    def units(self) -> int:
        """Units spent since the last reset."""
        return sum(call["cost"] for call in self.log())


class Corpus:
    """A corpus set with its key: the folder's own `key.json`, unless `key` names another."""

    def __init__(self, path, key: Path | None = None):
        self.path = Path(path)
        self.companies = mock_corpus.load(self.path).companies
        self.pages = [page for company in self.companies.values() for page in company.pages]
        key = Path(key) if key else self.path / mock_corpus.KEY_FILE
        self.key = json.loads(key.read_text(encoding="utf-8"))

    def expected(self, domain: str, field: str, *, stage: int, epoch: int = 0):
        """The acceptable values for a field: a key list means any one of them. A list field
        (`{"list": ...}` in the key) has one acceptable value, its array or None, so a list
        `[array_or_None]`; check with `fixtures.matches`."""
        value = self.key[domain]["expected"][str(stage)][str(epoch)][field]
        if isinstance(value, dict):
            return [value["list"]]
        return set(value) if isinstance(value, list) else {value}

    def company(self, plant: str, fields: tuple = FIELDS) -> dict:
        """The first company, by domain, whose key lists the plant on one of `fields`: its key
        entry plus `domain`.

        `plant` is a whole label such as `change:ceo@pages:1` or its leading part
        (`change`, `change:ceo`).
        """
        for domain in sorted(self.key):
            entry = self.key[domain]
            if any((label == plant or label.startswith((plant + ":", plant + "@")))
                   and label_parts(label)[1] in fields for label in entry.get("plants", ())):
                return {"domain": domain, **entry}
        raise LookupError(f"no company in {self.path} has the plant {plant!r}")

    def plain(self) -> list[str]:
        """The domains, sorted, that the key tags `plain` and gives `expected` values."""
        return sorted(domain for domain, entry in self.key.items()
                      if "expected" in entry and "plain" in entry.get("tags", ()))

    def plain_with(self, kind: str) -> str:
        """The first plain company whose plants include one of `kind` (e.g. `change`)."""
        for domain in self.plain():
            if any(label.startswith(kind + ":") for label in self.key[domain].get("plants", ())):
                return domain
        raise LookupError(f"no plain company in {self.path} has a {kind!r} plant")

    def planted(self, kind: str, scope: str | None = None,
                fields: tuple = FIELDS) -> list[tuple[str, str]]:
        """(domain, field) for every plant of `kind` on one of `fields` (in `scope`, if
        given), by domain."""
        return sorted((domain, field) for domain, entry in self.key.items()
                      for plant, field, where in map(label_parts, entry.get("plants", ()))
                      if plant == kind and scope in (None, where) and field in fields)

    def page(self, url: str, epoch: int = 0):
        """The page served at `url` in `epoch`, or None."""
        return next((page for page in self.pages if page.url == url and epoch in page.epochs),
                    None)

    def kind(self, url: str, epoch: int = 0) -> str:
        """A page's kind: its `Kind` line, or `aggregator` (stage 2)."""
        kind = header(self.page(url, epoch)).get("Kind")
        return kind if kind in KINDS else "aggregator"

    def published(self, url: str, epoch: int = 0) -> str | None:
        """A page's `Published` line when it is an RFC 3339 timestamp, else None (stage 2)."""
        stated = header(self.page(url, epoch)).get("Published")
        return stated if stated is not None and rfc3339(stated) else None

    def evidence(self, domain: str, epoch: int = 0, research: bool = True,
                 fields: tuple = FIELDS) -> list[dict]:
        """The key's supports of `fields` on the company's evidence in `epoch` (stage 1 §4,
        stage 2): its searchable pages and, with `research`, every page a `nimble` research
        entry cites with an excerpt that supports its claim. A page's text is what a browser
        shows."""
        supports = [s for s in self.key[domain]["supports"] if s["field"] in fields]
        labelled = {(s["url"], s["field"], json.dumps(s["value"]), collapse(s["excerpt"]))
                    for s in supports}
        claims = self.companies[domain].research.get("nimble", {}).get(str(epoch), [])
        cited = {claim["url"] for claim in claims if research and (
            claim["url"], claim["field"], json.dumps(claim["value"]),
            collapse(claim["excerpt"])) in labelled}
        found = []
        for support in supports:
            page = self.page(support["url"], epoch)
            if (page and (page.searchable or page.url in cited)
                    and collapse(support["excerpt"]) in collapse(prose(page.loaded))):
                found.append(support)
        return found

    def candidates(self, domain: str, epoch: int = 0) -> dict:
        """{field: {(url, value as JSON)}}: every value the company's evidence in `epoch`
        supports, with the page that supports it."""
        found = {}
        for support in self.evidence(domain, epoch):
            found.setdefault(support["field"], set()).add(
                (support["url"], json.dumps(support["value"])))
        return found

    def gathered(self, domain: str, epoch: int = 0, research: bool = True) -> dict:
        """{field: {value as JSON}} that the company's evidence in `epoch` supports; without
        `research`, only what its searchable pages support."""
        found = {}
        for support in self.evidence(domain, epoch, research):
            found.setdefault(support["field"], set()).add(json.dumps(support["value"]))
        return found

    def true_from(self, url: str, epoch: int = 0) -> str | None:
        """Stage 3: a page's valid `Effective` date, else the UTC date of its `Published`
        time, else None."""
        lines = header(self.page(url, epoch))
        effective = lines.get("Effective", "")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", effective):
            try:
                return date.fromisoformat(effective).isoformat()
            except ValueError:
                pass
        published = rfc3339(lines.get("Published", ""))
        return published.astimezone(timezone.utc).date().isoformat() if published else None

    def moved(self, domain: str, stage: int = 3) -> set:
        """The six fields whose expected value in epoch 1 differs from epoch 0."""
        return {name for name in FIELDS
                if self.expected(domain, name, stage=stage, epoch=0)
                != self.expected(domain, name, stage=stage, epoch=1)}

    def lookalike(self, url: str, epoch: int = 0) -> bool:
        """Stage 4: the page states `Kind: own` and its registrant is not its URL's host."""
        lines = header(self.page(url, epoch))
        return lines.get("Kind") == "own" and registrant(url, lines) != host(url)

    def origin(self, url: str, domain: str, epoch: int = 0, hops: int = 0) -> str:
        """Stage 4: the origin of the page at `url`, a page of the company `domain`: its
        `First-Published-By` domain, else, when its `Canonical` is another URL, the origin of
        the page there (at most three such hops; the URL's host when none is served), else
        the company's domain for a lookalike, else its registrant."""
        lines = header(self.page(url, epoch))
        if lines.get("First-Published-By"):
            return normalise(lines["First-Published-By"])
        canonical = lines.get("Canonical")
        if canonical and canonical != url:
            if hops < 3 and self.page(canonical, epoch):
                return self.origin(canonical, domain, epoch, hops + 1)
            return host(canonical)
        if self.lookalike(url, epoch):
            return domain
        return registrant(url, lines)

    def rendered(self, sole: bool = False) -> list[tuple[str, str]]:
        """(domain, field) for every field planted on a page whose loaded text differs from
        what extract serves, by domain. `sole`: only fields no other page or research entry
        states."""
        return self.planted("rendered", "sole" if sole else None)

    def stale(self, domain: str, field: str):
        """The value of `field` that only the extract-served text of a page supports."""
        for support in self.key[domain].get("supports", ()):
            if support["field"] == field and support.get("static"):
                return support["value"]
        raise LookupError(f"{domain} has no stale value for {field}")

    def carries(self, url: str, excerpt: str) -> bool:
        """Whether a page at `url`, in any epoch, has the excerpt in its prose, as served or
        as loaded.

        A blank excerpt is never carried.
        """
        wanted = collapse(excerpt)
        return bool(wanted) and any(
            wanted in collapse(prose(text)) for page in self.pages if page.url == url
            for text in (page.served, page.loaded))


RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})")


def rfc3339(text: str) -> datetime | None:
    """An RFC 3339 timestamp as an aware datetime, or None when `text` is not one."""
    if not RFC3339.fullmatch(text):
        return None
    try:
        return datetime.fromisoformat(text.upper().replace("Z", "+00:00"))
    except ValueError:
        return None


def prose(text: str) -> str:
    """A served or loaded page's prose: the text after its header."""
    return text.partition("\n\n")[2]


def normalise(domain: str) -> str:
    """A domain as stage 1 normalises it: trimmed, lowercased, no trailing `.` or `www.`."""
    domain = domain.strip().lower()
    return domain.removesuffix(".").removeprefix("www.")


def host(url: str) -> str:
    """The normalised host of a URL."""
    return normalise(urlsplit(url).hostname or "")


def registrant(url: str, lines: dict) -> str:
    """Stage 4: a page's `Registrant` domain, normalised, else the host of its URL."""
    stated = normalise(lines.get("Registrant", ""))
    return stated or host(url)


def assert_citations(body: dict, corpus: Corpus) -> None:
    """Raise FabricationError for a citation or candidate (stage 2) whose excerpt is not text
    of the page at its URL."""
    for name, field in body["fields"].items():
        for cite in field["citations"] + field.get("candidates", []):
            if not corpus.carries(cite["url"], cite["excerpt"]):
                raise FabricationError(
                    f"{name}: excerpt {cite['excerpt'][:80]!r} is not on any page at {cite['url']}")


def gatherings(calls: list[dict], domain: str) -> int:
    """How many builds of `domain` the call log shows: each makes exactly one search, through
    any provider and answered without an error, whose query is exactly the domain."""
    return sum(1 for call in calls if call["method"] == "search"
               and call["query"] == domain and call["status"] == 200)


def served(calls: list[dict], provider: str, url: str, excerpt: str) -> bool:
    """Whether `provider` served the excerpt for `url` in any logged call."""
    wanted = collapse(excerpt)
    return bool(wanted) and any(
        item["url"] == url and wanted in collapse(item["text"])
        for call in calls if call["provider"] == provider for item in call["served"])
