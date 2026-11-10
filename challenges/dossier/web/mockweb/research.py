"""Resolving a research run's answer from the corpus."""
from dataclasses import dataclass

FIELDS = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")


@dataclass(frozen=True)
class Claim:
    """A field's value and the excerpt of the page at `url` cited for it."""
    field: str
    value: object
    url: str
    excerpt: str


def properties(schema):
    """The property names an output schema asks for."""
    props = schema.get("properties") if isinstance(schema, dict) else None
    return list(props) if isinstance(props, dict) else []


def schema_fields(schema):
    """The sorted property names of an output schema, or None without a schema."""
    return sorted(properties(schema)) if isinstance(schema, dict) else None


def resolve(corpus, provider, epoch, query, schema):
    """One claim per Dossier field the schema names that the company's entries fill."""
    company = corpus.company_in(query)
    if company is None:
        return []
    entries = company.research.get(provider, {}).get(str(epoch), [])
    claims = []
    for name in properties(schema):
        entry = next((entry for entry in entries if entry["field"] == name), None)
        if name in FIELDS and entry is not None:
            claims.append(Claim(name, entry["value"], entry["url"], entry["excerpt"]))
    return claims


def structured(schema, claims):
    """The answer object: every schema property, null where no claim fills it."""
    values = {claim.field: claim.value for claim in claims}
    return {name: values.get(name) for name in properties(schema)}
