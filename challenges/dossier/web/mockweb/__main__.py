"""Serve the mock: `python -m mockweb` reads `/data/corpus` and listens on port 8080."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import admin, browserbase, browsers, kernel, nimble, tavily
from .corpus import load
from .pages import PageServer

PORT = 8080
REQUEST_QUEUE_SIZE = 128
CORPUS = Path("/data/corpus")
CERTIFICATE, KEY = Path("/app/cert.pem"), Path("/app/key.pem")
ROUTES = {"/nimble": nimble.route, "/tavily": tavily.route}
# Browser vendors' routes also take the Host header, to name their DevTools URLs.
BROWSER_ROUTES = {"/kernel": kernel.route, "/browserbase": browserbase.route}


class Handler(BaseHTTPRequestHandler):
    """Dispatches by path prefix to a provider or to the admin API."""
    protocol_version = "HTTP/1.1"
    state = None

    def do_GET(self):  # pylint: disable=invalid-name
        """Route a GET; a websocket upgrade on a session's DevTools path is relayed."""
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self.devtools()
        else:
            self.dispatch("GET")

    def do_DELETE(self):  # pylint: disable=invalid-name
        """Route a DELETE."""
        self.dispatch("DELETE")

    def do_POST(self):  # pylint: disable=invalid-name
        """Route a POST."""
        self.dispatch("POST")

    def dispatch(self, verb):
        """Answer from the admin API or the provider the path prefix names, else 404."""
        path = unquote(urlsplit(self.path).path)
        try:
            body = self.read_body()
        except ValueError:
            self.reply(400, admin.error(400, "the body is not a JSON object"))
            return
        prefix, _, rest = path.partition("/")[2].partition("/")
        if prefix == "_mock":
            answer = admin.route(self.state, verb, f"/{rest}",
                                 self.headers.get("X-Mock-Admin"), body)
        elif f"/{prefix}" in ROUTES:
            answer = ROUTES[f"/{prefix}"](self.state, verb, f"/{rest}", body)
        elif f"/{prefix}" in BROWSER_ROUTES:
            answer = BROWSER_ROUTES[f"/{prefix}"](self.state, verb, f"/{rest}", body,
                                                  self.headers.get("Host", f"web:{PORT}"))
        else:
            answer = None
        self.reply(*(answer or (404, admin.error(404, "not found"))))

    def devtools(self):
        """Relay `/<vendor>/cdp/<session id>` to that session's Chromium, with the path and
        Host rewritten: Chromium accepts only an IP or `localhost` as the Host."""
        vendor, cdp, session_id = (unquote(urlsplit(self.path).path).strip("/").split("/")
                                   + ["", "", ""])[:3]
        session = self.state.browsers.get(vendor, session_id) if cdp == "cdp" else None
        if session is None:
            self.reply(404, admin.error(404, "no such browser session"))
            return
        lines = [f"GET {session.browser_path} HTTP/1.1",
                 f"Host: 127.0.0.1:{session.devtools_port}"]
        lines += [f"{name}: {value}" for name, value in self.headers.items()
                  if name.lower() != "host"]
        head = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
        self.close_connection = True  # pylint: disable=attribute-defined-outside-init
        browsers.relay(self.state.browsers, session, self.connection, head, b"")

    def read_body(self):
        """The request's JSON object body, {} when there is none."""
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(body, dict):
            raise ValueError(body)
        return body

    def reply(self, status, payload):
        """Send a JSON payload, or an empty body when `payload` is None."""
        data = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(status)
        if payload is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Server(ThreadingHTTPServer):
    """A threading server whose listen backlog takes a burst of concurrent builds."""
    request_queue_size = REQUEST_QUEUE_SIZE
    daemon_threads = True


def build_server(port, corpus, token, launch=browsers.Chromium):
    """A server over the corpus at `corpus`, not yet serving; token "" disables admin.
    `launch(address)` starts a session's browser."""
    state = admin.State(load(corpus), token, browsers.Pool(launch))
    handler = type("BoundHandler", (Handler,), {"state": state})
    return Server(("", port), handler)


def reap(pool):
    """Close idle browser sessions, once a second, for the server's lifetime."""
    while True:
        time.sleep(1)
        pool.reap()


def serve(port, corpus, token):
    """Serve until interrupted, with the page server for browser sessions beside it."""
    with build_server(port, corpus, token) as server:
        state = server.RequestHandlerClass.state
        pages = PageServer(state, CERTIFICATE, KEY)
        threading.Thread(target=pages.serve_forever, daemon=True).start()
        threading.Thread(target=reap, args=(state.browsers,), daemon=True).start()
        print(f"mock web on :{port}, corpus {corpus}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    serve(PORT, CORPUS, os.environ.get("MOCK_ADMIN_TOKEN", ""))
