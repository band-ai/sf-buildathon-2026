"""Browserbase's Sessions and Agents API routes, as WebRouter 0.12.0's Browserbase providers
call them. A session is released by updating it; its `/debug` route is not served. An agent
run reads the first URL in its task and completes at once, with that page's text, as a
browser shows it, as its summary."""
import re
import time

from .admin import error

PROVIDER = "browserbase"
OPEN_COST = 2
LOAD_COST = 1
AGENT_COST = 4
URL = re.compile(r"https?://\S+")
SESSION = re.compile(r"/v1/sessions/([^/]+)")
RUN = re.compile(r"/v1/agents/runs/([^/]+)(/stop)?")


def session_payload(session, host, status="RUNNING"):
    """A session as Browserbase describes it. Its DevTools URL is on the host the client
    used."""
    expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3600))
    return {"id": session.id, "status": status, "createdAt": session.created,
            "expiresAt": expires, "keepAlive": False, "region": "us-west-2",
            "connectUrl": f"ws://{host}/browserbase/cdp/{session.id}"}


def route(state, verb, path, body, host):
    """Answer a Browserbase request as `(status, payload)`, or None for a 404."""
    if (verb, path) == ("POST", "/v1/sessions"):
        return state.open_session(PROVIDER, body, OPEN_COST, lambda s: session_payload(s, host))
    if (verb, path) == ("POST", "/v1/agents/runs"):
        return start(state, body)
    if SESSION.fullmatch(path):
        return session_route(state, verb, SESSION.fullmatch(path)[1], body, host)
    match = RUN.fullmatch(path)
    run = match and state.run(PROVIDER, match[1])
    if not run:
        return None
    if match[2]:
        return (409, error(409, "the run has already finished")) if verb == "POST" else None
    return (200, run) if verb == "GET" else None


def session_route(state, verb, session_id, body, host):
    """Read a session, or release it by updating its status."""
    session = state.browsers.get(PROVIDER, session_id)
    if session is None:
        return 404, error(404, "session not found")
    if verb == "GET":
        return 200, session_payload(session, host)
    if verb == "POST" and body.get("status") == "REQUEST_RELEASE":
        state.browsers.close(PROVIDER, session.id)
        return 200, session_payload(session, host, "COMPLETED")
    return None


def start(state, body):
    """Run the agent on the first URL of its task: completed with the page's text, or
    failed, at no cost, when the task names no page of the current epoch."""
    task = body.get("task")
    found = URL.search(task) if isinstance(task, str) else None
    url = found[0].rstrip(".,;)") if found else None

    def answer():
        page = state.corpus.page(state.epoch, url) if url else None
        run = {"runId": None, "status": "COMPLETED" if page else "FAILED"}
        if page is None:
            run["cause"] = {"message": "the task names no page the agent could open"}
            return 200, run, 0, []
        run["result"] = {"summary": page.loaded, "stepsTaken": 1}
        return 200, run, AGENT_COST, [(url, page.loaded)]

    status, run = state.call(PROVIDER, "browse", body, answer, urls=[url] if url else [])
    if status == 200:
        run["runId"] = state.add_run(PROVIDER, run)
    return status, run
