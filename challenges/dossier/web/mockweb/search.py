"""Deterministic keyword ranking: BM25 over title and served text, ties broken by URL.

Each provider perturbs the scores by its own fixed noise, so providers rank the same pages
differently, and each always the same way.
"""
import functools
import hashlib
import math
import re
from collections import Counter

from .corpus import DOMAIN, NO_TRAITS, domains_in

K1 = 1.2
B = 0.75
WORD = re.compile(r"[a-z0-9]+")
MAX_RESULTS = 10


def tokens(text):
    """Each `.test` host name as one term, then lowercased runs of letters and digits."""
    lowered = text.lower()
    return domains_in(lowered) + WORD.findall(DOMAIN.sub(" ", lowered))


@functools.cache
def page_terms(page):
    """The term counts of a page's title and served text, counted once per page; read only."""
    return Counter(tokens(f"{page.title} {page.served}"))


def draw(seed, provider, key):
    """A fixed fraction in [0, 1): the first 32 bits of sha256(f"{seed}:{provider}:{key}")
    over 2**32. Ranking noise and the weather both draw from it."""
    digest = hashlib.sha256(f"{seed}:{provider}:{key}".encode()).hexdigest()
    return int(digest[:8], 16) / 2 ** 32


def jitter(seed, provider, url):
    """A fixed number in [-1, 1) for a provider and a page."""
    return 2 * draw(seed, provider, url) - 1


def rank(pages, query, limit, *, provider=None, traits=None):
    """The most relevant searchable pages, a named company's pages first, at most
    MAX_RESULTS of them.

    A page matches when it shares a word with the query or belongs to a company
    whose domain the query contains. With a `provider`, each match's score is scaled
    by `1 + noise * jitter`, the noise that provider has in `traits`; without one, or
    without noise, the ranking is plain BM25.
    """
    traits = traits or NO_TRAITS
    noise = traits["providers"].get(provider, {}).get("noise", 0)
    seed = traits["seed"]
    pages = [page for page in pages if page.searchable]
    named = set(domains_in(query))
    terms = sorted(set(tokens(query)))
    docs = [page_terms(page) for page in pages]
    average = sum(sum(doc.values()) for doc in docs) / len(docs) if docs else 0.0
    frequency = Counter(term for doc in docs for term in terms if term in doc)

    def score(doc):
        length = sum(doc.values())
        total = 0.0
        for term in terms:
            count = doc[term]
            if count:
                idf = math.log(1 + (len(docs) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                total += idf * count * (K1 + 1) / (count + K1 * (1 - B + B * length / average))
        return total

    scored = [(page.company not in named, score(doc), page) for page, doc in zip(pages, docs)]
    hits = [(other, -bm25 * (1 + noise * jitter(seed, provider, page.url)), page.url, page)
            for other, bm25, page in scored if not other or bm25 > 0]
    return [entry[3] for entry in sorted(hits, key=lambda entry: entry[:3])][
        :min(limit, MAX_RESULTS)]


def ranked(state, provider, query, limit, default):
    """What a provider's search returns for the query in the state's current epoch, or
    None unless the query is a non-empty string and the limit a non-negative integer. A
    missing or null limit is the provider's `default`."""
    limit = default if limit is None else limit
    if (not isinstance(query, str) or not query or not isinstance(limit, int)
            or isinstance(limit, bool) or limit < 0):
        return None
    return rank(state.corpus.pages(state.epoch), query, limit, provider=provider,
                traits=state.corpus.traits)
