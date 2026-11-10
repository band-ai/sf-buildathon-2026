"""The Tavily routes tavily-python 0.8 calls for search and extract."""
# pylint: disable=duplicate-code  # Tavily and Nimble name their search fields alike
from .admin import error
from .corpus import SNIPPET_CHARS
from .search import ranked

PROVIDER = "tavily"
COST = {"lite": 8, "fast": 16, "deep": 16}
EXTRACT_COST = 2
DEFAULT_RESULTS = 5
CONTENT_CHARS = {"lite": SNIPPET_CHARS, "fast": 450, "deep": 450}


def route(state, verb, path, body):
    """Answer a Tavily request as `(status, payload)`, or None for a 404."""
    if verb == "POST" and path == "/search":
        return search(state, body)
    if verb == "POST" and path == "/extract":
        return extract(state, body)
    return None


def depth_of(body):
    """WebRouter's depth: raw content asked for is deep, `advanced` alone is fast, else lite."""
    if body.get("include_raw_content"):
        return "deep"
    return "fast" if body.get("search_depth") == "advanced" else "lite"


def search(state, body):
    """Rank the pages for the query: a snippet each, and the served page when deep."""
    query, depth = body.get("query"), depth_of(body)

    def answer():
        pages = ranked(state, PROVIDER, query, body.get("max_results"), DEFAULT_RESULTS)
        if pages is None:
            return 400, error(400, "query and a non-negative integer "
                              "max_results are required"), 0, []
        results = [{"title": page.title, "url": page.url,
                    "content": page.text[:CONTENT_CHARS[depth]],
                    "raw_content": page.served if depth == "deep" else None} for page in pages]
        payload = {"query": query, "answer": None, "images": [], "results": results,
                   "response_time": 0.0, "request_id": "search"}
        served = [(item["url"], item["raw_content"] or item["content"]) for item in results]
        return 200, payload, COST[depth], served

    return state.call(PROVIDER, "search", body, answer, depth=depth, query=query,
                      max_results=body.get("max_results"))


def extract(state, body):
    """Each URL's served page, or a failed result for a URL with no page; every URL bills."""
    urls = body.get("urls")
    urls = [urls] if isinstance(urls, str) else urls

    def answer():
        pages = state.corpus.pages_at(state.epoch, urls)
        if pages is None:
            return 400, error(400, "urls must be a URL or a list of URLs"), 0, []
        payload = {
            "results": [{"url": page.url, "raw_content": page.served, "images": []}
                        for page in pages if page is not None],
            "failed_results": [{"url": url, "error": "no page at this URL"}
                               for url, page in zip(urls, pages) if page is None],
            "response_time": 0.0, "request_id": "extract"}
        return (200, payload, EXTRACT_COST * len(urls),
                [(page.url, page.served) for page in pages if page is not None])

    return state.call(PROVIDER, "extract", body, answer,
                      urls=urls if isinstance(urls, list) else [])
