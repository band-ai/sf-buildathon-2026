"""The page server: every `.test` page of the current epoch over HTTPS, as a browser in a
session loads it. A page's HTML holds the text extract serves and a script that writes in
what a browser shows, then the page's disclosure controls: buttons with
`aria-expanded="false"`, each disclosing its text and inner controls when clicked. Every page
it answers with 200 is one load, billed to the session whose Chromium asked: each session's
Chromium reaches the server from its own loopback address."""
import html
import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import browserbase, kernel
from .corpus import unfolded

PORT = 443
LOAD_COST = {"kernel": kernel.LOAD_COST, "browserbase": browserbase.LOAD_COST}
# fold(parent, folds) appends a control to `parent` per (label, text, inner controls). Each
# label and each disclosed text starts a line, so innerText and textContent agree.
FOLD = """let next = 0;
const fold = (parent, folds) => {
  for (const [label, text, inner] of folds) {
    const button = document.createElement("button");
    const region = document.createElement("span");
    region.id = "disclosed-" + next++;
    region.hidden = true;
    button.textContent = label;
    button.setAttribute("aria-controls", region.id);
    button.setAttribute("aria-expanded", "false");
    button.addEventListener("click", () => {
      if (button.getAttribute("aria-expanded") === "true") return;
      button.setAttribute("aria-expanded", "true");
      region.hidden = false;
      if (text) region.append("\\n" + text);
      fold(region, inner);
    });
    parent.append("\\n", button, region);
  }
};"""


def literal(value):
    """A value as a JavaScript literal that cannot end the script element."""
    return json.dumps(value).replace("</", "<\\/")


def document(page):
    """The HTML a browser loads for a page."""
    shown = literal(page.loaded.removesuffix(unfolded(page.folds)))
    return (f"<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(page.title)}</title></head><body>"
            f"<pre id=\"page\">{html.escape(page.served)}</pre>"
            f"<script>{FOLD}\nconst page = document.getElementById(\"page\");\n"
            f"page.textContent = {shown};\nfold(page, {literal(page.folds)});</script>"
            f"</body></html>")


class PageHandler(BaseHTTPRequestHandler):
    """Answers a session's page loads."""
    protocol_version = "HTTP/1.1"
    state = None

    def do_GET(self):  # pylint: disable=invalid-name
        """Serve the page at https://<Host><path>, or 404."""
        session = self.state.browsers.session_for_address(self.connection.getsockname()[0])
        url = f"https://{(self.headers.get('Host') or '').split(':')[0]}{self.path}"
        page = self.state.corpus.page(self.state.epoch, url)
        if session is None or page is None:
            self.reply(404, b"not found", "text/plain")
            return
        self.state.log.record(session.vendor, "load", cost=LOAD_COST[session.vendor],
                              status=200, urls=[url], served=[(url, page.loaded)],
                              session=session.id)
        self.reply(200, document(page).encode(), "text/html; charset=utf-8")

    def reply(self, status, body, kind):
        """Send a body the browser must not cache."""
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):  # pylint: disable=arguments-differ
        """Quiet: the call log records every load."""


class PageServer(ThreadingHTTPServer):
    """A threading HTTPS server; each connection's TLS handshake runs on its own thread."""
    daemon_threads = True

    def __init__(self, state, certificate, key, port=PORT):
        handler = type("BoundPageHandler", (PageHandler,), {"state": state})
        super().__init__(("", port), handler)
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(certificate, key)

    def finish_request(self, request, client_address):
        """Wrap the connection in TLS, then answer it."""
        try:
            request = self.context.wrap_socket(request, server_side=True)
        except (ssl.SSLError, OSError):
            return
        try:
            super().finish_request(request, client_address)
        finally:
            request.close()
