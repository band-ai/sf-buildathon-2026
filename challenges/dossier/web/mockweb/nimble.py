"""The Nimble routes nimble-python 1.6 calls for search, extract and agent runs."""
import re

from . import research
from .admin import error
from .search import ranked

PROVIDER = "nimble"
COST = {"lite": 1, "fast": 5, "deep": 15}
EXTRACT_COST = 1
RENDER_COST = 3     # an extract with `render: true`, which loads the page in a browser
RESEARCH_COST = 25
DEFAULT_RESULTS = 10
BODY_CHARS = 1500
FORMATS = ("markdown", "html")
TIMESTAMP = "2026-01-01T00:00:00Z"
RUN = re.compile(r"/v2/agents/([^/]+)/runs/([^/]+)(/result)?")


def route(state, verb, path, body):
    """Answer a Nimble request as `(status, payload)`, or None for a 404. The template
    catalogue is empty, so every template name is not found."""
    if verb == "POST" and path == "/v2/search":
        return search(state, body)
    if verb == "POST" and path == "/v2/extract":
        return extract(state, body)
    if verb == "POST" and path == "/v2/agents/runs":
        return start(state, body)
    if verb == "GET" and path == "/v2/extract/templates":
        return 200, {"items": [], "total": 0, "offset": 0, "limit": 0}
    match = RUN.fullmatch(path)
    if verb == "GET" and match:
        return poll(state, *match.groups())
    return None


def depth_of(body):
    """WebRouter's depth: `full_content` is deep, `standard` alone is fast, else lite."""
    if body.get("full_content"):
        return "deep"
    return "fast" if body.get("search_depth") == "standard" else "lite"


def search(state, body):
    """Rank the pages for the query, at the depth the request implies."""
    query, depth = body.get("query"), depth_of(body)

    def answer():
        pages = ranked(state, PROVIDER, query, body.get("max_results"), DEFAULT_RESULTS)
        if pages is None:
            return 400, error(400, "query and a non-negative integer "
                              "max_results are required"), 0, []
        results = [result(position, page, depth) for position, page in enumerate(pages, 1)]
        texts = [item["description"] or item["content"] for item in results]
        payload = {"request_id": "search", "total_results": len(results),
                   "results": results}
        return 200, payload, COST[depth], [(page.url, text) for page, text in zip(pages, texts)]

    return state.call(PROVIDER, "search", body, answer, depth=depth, query=query,
                      max_results=body.get("max_results"))


def result(position, page, depth):
    """One search result: a snippet for lite, else the served text, cut short for fast."""
    body = {"lite": "", "fast": page.served[:BODY_CHARS], "deep": page.served}[depth]
    return {"title": page.title, "url": page.url,
            "description": page.snippet if depth == "lite" else "", "content": body,
            "metadata": {"position": position, "entity_type": "OrganicResult",
                         "country": "US", "locale": "en"}}


def extract(state, body):
    """A page's served text, or with `render: true` the text a browser shows once it has
    loaded, before any disclosure control is activated; or Nimble's in-band failure for a URL
    with no page."""
    url, render = body.get("url"), body.get("render") is True
    cost = RENDER_COST if render else EXTRACT_COST

    def answer():
        page = state.corpus.page(state.epoch, url)
        payload = {"task_id": "extract", "url": url, "metadata": {}}
        if page is None:
            payload.update(status="fatal", status_code=404, data={},
                           warnings=["no page at this URL"])
            return 200, payload, cost, []
        text = page.initial if render else page.served
        formats = [name for name in body.get("formats") or ["html"] if name in FORMATS]
        payload.update(status="success", status_code=200,
                       data={name: text for name in formats})
        return 200, payload, cost, [(page.url, text)]

    return state.call(PROVIDER, "extract", body, answer, urls=[url])


def run_status(run_id, run, status):
    """A run as the create and status routes report it."""
    return {"id": run_id, "web_search_agent_id": run["agent"], "status": status,
            "is_active": status == "queued", "effort": run["effort"],
            "interaction_id": run_id, "prompt": run["query"], "created_at": TIMESTAMP,
            "completed_at": TIMESTAMP if status == "completed" else None}


def start(state, body):
    """Create a research run, resolving its answer now."""
    query, schema = body.get("input"), body.get("output_schema")

    def answer():
        if not isinstance(query, str) or not query or not isinstance(schema, (dict, type(None))):
            return 400, error(400, "input and an object output_schema are required"), 0, []
        claims = research.resolve(state.corpus, PROVIDER, state.epoch, query, schema)
        run = {"agent": f"agent-{body.get('agent_name') or 'default'}", "query": query,
               "effort": body.get("effort") or "low", "schema": schema, "claims": claims,
               "titles": titles(state, claims), "polled": False}
        run_id = state.add_run(PROVIDER, run)
        return (200, run_status(run_id, run, "queued"), RESEARCH_COST,
                [(claim.url, claim.excerpt) for claim in claims])

    return state.call(PROVIDER, "research", body, answer, query=query,
                      fields=research.schema_fields(schema))


def titles(state, claims):
    """The titles of the cited pages served in the current epoch."""
    pages = (state.corpus.page(state.epoch, claim.url) for claim in claims)
    return {page.url: page.title for page in pages if page is not None}


def poll(state, agent_id, run_id, wants_result):
    """A run's status, completed from the first poll on, or its result once completed."""
    run = state.run(PROVIDER, run_id)
    if run is None or run["agent"] != agent_id:
        return 404, error(404, "no such run")
    if not wants_result:
        run["polled"] = True
        return 200, run_status(run_id, run, "completed")
    if not run["polled"]:
        return 409, error(409, "the run has not completed")
    return 200, {"run": run_status(run_id, run, "completed"), "output": output(run)}


def output(run):
    """A finished run's output: the answer object and a claim per filled field."""
    claims, names = run["claims"], run["titles"]
    trust = {
        "confidence": "high", "reasoning": "",
        "claims": [{"path": f"$.{claim.field}", "confidence": "high", "reasoning": "",
                    "citations": [{"url": claim.url, "title": names.get(claim.url, ""),
                                   "excerpts": [claim.excerpt]}]} for claim in claims],
        "sources": [{"url": url, "title": names.get(url, ""), "type": "primary"}
                    for url in dict.fromkeys(claim.url for claim in claims)]}
    if research.properties(run["schema"]):
        return {"type": "json", "content": research.structured(run["schema"], claims),
                "trust": trust}
    return {"type": "text", "content": "", "trust": trust}
