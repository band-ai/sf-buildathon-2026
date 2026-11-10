"""Loading a corpus set: one JSON file per company, the set's `traits.json`, never its
`key.json`."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

KEY_FILE = "key.json"
TRAITS_FILE = "traits.json"
NO_TRAITS = {"seed": 0, "providers": {}}
SNIPPET_CHARS = 300
DOMAIN = re.compile(r"(?<![a-z0-9.-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+test(?![a-z0-9-])")


@dataclass(frozen=True)
class Page:  # pylint: disable=too-many-instance-attributes
    """One corpus page entry, with the text the mock serves for it."""
    company: str
    url: str
    title: str
    served: str
    epochs: frozenset
    searchable: bool
    shown: str | None = None
    folds: tuple = ()

    @property
    def loaded(self):
        """What a browser shows once the page has loaded and every disclosure control on it
        has been activated: `served`, unless the page is browser-only."""
        return self.served if self.shown is None else self.shown

    @property
    def initial(self):
        """What a browser shows once the page has loaded, before any disclosure control is
        activated: what Nimble's extract with render serves."""
        return self.loaded.removesuffix(unfolded(self.folds)) + unfolded(self.folds, 0)

    @property
    def browser_only(self):
        """Whether a browser shows other text than search and extract serve."""
        return self.shown is not None

    @property
    def text(self):
        """The page's prose: the served text after its header."""
        return self.served.partition("\n\n")[2]

    @property
    def snippet(self):
        """The first characters of the page's prose."""
        return self.text[:SNIPPET_CHARS]

    @classmethod
    def from_entry(cls, company, entry):
        """A page from its corpus entry, for the company with domain `company`. Every
        provider serves every page; an older entry's `providers` list is ignored. A page with
        disclosure controls serves what shows before any of them is activated."""
        static, folds = entry.get("static_text"), freeze(entry.get("disclosures") or ())
        return cls(company=company, url=entry["url"], title=entry["title"],
                   served=render(entry, collapsed(entry) if static is None else static),
                   epochs=frozenset(entry["epochs"]), searchable=entry.get("searchable", True),
                   shown=None if static is None and not folds else render(entry), folds=folds)


def freeze(disclosures):
    """A corpus entry's `disclosures` as (control label, disclosed text, inner controls)."""
    return tuple((item["control"], item.get("text", ""), freeze(item.get("disclosures") or ()))
                 for item in disclosures)


def unfolded(folds, depth=-1):
    """What disclosure controls add to a page's text with those fewer than `depth` levels deep
    activated, every one by default: each control's label on a line of its own, then, once it
    is activated, the text it discloses and its own controls."""
    return "".join(f"\n{label}" + ((f"\n{text}" if text else "") + unfolded(inner, depth - 1)
                                    if depth else "") for label, text, inner in folds)


def collapsed(entry, depth=0):
    """A page's text with only its disclosure controls fewer than `depth` levels deep
    activated, none by default; None when it has no control. Its `text` ends with what the
    controls disclose (`unfolded`)."""
    folds = freeze(entry.get("disclosures") or ())
    if not folds:
        return None
    return entry["text"].removesuffix(unfolded(folds)) + unfolded(folds, depth)


def render(entry, text=None):
    """Header lines, an empty line, then `text`, by default the page's text."""
    lineage = entry["lineage"]
    headers = [("Kind", entry["kind"]), ("Published", entry.get("published_at")),
               ("Effective", entry.get("true_from")), ("Registrant", lineage["registrant"]),
               ("Canonical", lineage.get("canonical")),
               ("First-Published-By", lineage.get("first_published_by")),
               ("Facts", json.dumps(entry["facts"], ensure_ascii=False)
                if entry.get("facts") else None)]
    lines = [f"{name}: {value}" for name, value in headers if value is not None]
    return "\n".join(lines) + "\n\n" + (entry["text"] if text is None else text)


@dataclass(frozen=True)
class Company:
    """A company's names, pages and research entries."""
    domain: str
    names: tuple
    pages: tuple
    research: dict


class Corpus:
    """Every company of one corpus set, keyed by domain, and the set's provider traits."""

    def __init__(self, companies, traits=None):
        self.companies = companies
        self.traits = {**NO_TRAITS, **(traits or {})}

    def pages(self, epoch):
        """The pages served in an epoch."""
        return [page for company in self.companies.values() for page in company.pages
                if epoch in page.epochs]

    def page(self, epoch, url):
        """The page served at `url` in an epoch, or None."""
        return next((page for page in self.pages(epoch) if page.url == url), None)

    def pages_at(self, epoch, urls):
        """The page served at each URL in an epoch, None where there is none; or None
        unless `urls` is a non-empty list of strings."""
        if not isinstance(urls, list) or not urls or not all(isinstance(url, str) for url in urls):
            return None
        return [self.page(epoch, url) for url in urls]

    def company_in(self, query):
        """The company a query names: by its first corpus `.test` domain, else by a name."""
        for domain in domains_in(query):
            if domain in self.companies:
                return self.companies[domain]
        lowered = query.lower()
        found = [(lowered.find(name.lower()), company.domain)
                 for company in self.companies.values() for name in company.names
                 if name.lower() in lowered]
        return self.companies[min(found)[1]] if found else None


def domains_in(text):
    """The `.test` host names in a text, in order, a leading `www.` removed."""
    return [domain.removeprefix("www.") for domain in DOMAIN.findall(text.lower())]


def load(path):
    """Read every company file of a corpus set, and its traits file when it has one."""
    companies = {}
    for file in sorted(Path(path).glob("*.json")):
        if file.name in (KEY_FILE, TRAITS_FILE):
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        domain = data["domain"]
        companies[domain] = Company(
            domain=domain, names=tuple(data.get("names", ())),
            pages=tuple(Page.from_entry(domain, entry) for entry in data["pages"]),
            research=data.get("research", {}))
    if not companies:
        raise FileNotFoundError(f"no company files in {path}")
    traits = Path(path) / TRAITS_FILE
    return Corpus(companies, json.loads(traits.read_text(encoding="utf-8"))
                  if traits.exists() else None)
