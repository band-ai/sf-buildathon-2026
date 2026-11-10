"""Kernel's Browsers API routes, as WebRouter 0.12.0's `KernelBrowserProvider` calls them:
open a session, read it, delete it."""
PROVIDER = "kernel"
OPEN_COST = 0
LOAD_COST = 1


def session_payload(session, host):
    """A session as Kernel describes it. Its DevTools URL is on the host the client used."""
    return {"session_id": session.id, "cdp_ws_url": f"ws://{host}/kernel/cdp/{session.id}",
            "created_at": session.created, "headless": True, "stealth": False,
            "timeout_seconds": 60}


def gone():
    """Kernel's answer for a session it no longer has."""
    return 404, {"code": "not_found", "message": "browser session not found"}


def route(state, verb, path, body, host):
    """Answer a Kernel request as `(status, payload)`, or None for a 404."""
    if (verb, path) == ("POST", "/browsers"):
        return state.open_session(PROVIDER, body, OPEN_COST, lambda s: session_payload(s, host))
    session_id = path.removeprefix("/browsers/")
    if session_id == path or "/" in session_id:
        return None
    if verb == "GET":
        session = state.browsers.get(PROVIDER, session_id)
        return (200, session_payload(session, host)) if session else gone()
    if verb == "DELETE":
        return (204, None) if state.browsers.close(PROVIDER, session_id) else gone()
    return None
