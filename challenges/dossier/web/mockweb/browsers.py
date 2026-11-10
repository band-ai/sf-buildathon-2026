"""Browser sessions: one headless Chromium per session, which resolves every `.test` host to
its own loopback address, where the page server answers. The address tells the page server
which session a page load belongs to."""
import os
import pwd
import select
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CAP = 4
IDLE_SECONDS = 60.0
START_SECONDS = 20.0
ADDRESSES = [f"127.0.0.{n}" for n in range(2, 255)]
USER = "chromium"  # cannot read /data, where the corpus is mounted
FLAGS = ["--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
         "--no-first-run", "--disable-background-networking", "--disable-sync",
         "--ignore-certificate-errors", "--remote-debugging-port=0"]


class Chromium:  # pylint: disable=too-few-public-methods
    """A headless Chromium process, run as USER in its own process group, and its DevTools
    endpoint."""

    def __init__(self, address):
        self.profile = tempfile.mkdtemp(prefix="chromium-")
        account = pwd.getpwnam(USER)
        os.chown(self.profile, account.pw_uid, account.pw_gid)
        rules = f"MAP *.test {address}, MAP * ~NOTFOUND"
        self.process = subprocess.Popen(  # pylint: disable=consider-using-with
            [shutil.which("chromium"), *FLAGS, f"--user-data-dir={self.profile}",
             f"--host-resolver-rules={rules}", "about:blank"], user=USER, group=account.pw_gid,
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        active = Path(self.profile) / "DevToolsActivePort"
        deadline = time.monotonic() + START_SECONDS
        while not (active.exists() and len(active.read_text().split()) == 2):
            if self.process.poll() is not None or time.monotonic() > deadline:
                self.close()
                raise OSError("chromium did not start")
            time.sleep(0.05)
        port, self.path = active.read_text().split()
        self.port = int(port)

    def close(self):
        """Stop the browser and every process it started, and remove its profile."""
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait()
        shutil.rmtree(self.profile, ignore_errors=True)


@dataclass
class Session:  # pylint: disable=too-many-instance-attributes
    """One open session of one vendor."""
    id: str
    vendor: str
    address: str
    browser: Any  # a Chromium, or what a test launcher returns; None while it starts
    opened_at: float
    idle_since: float
    clients: int = 0
    created: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                               time.gmtime()))

    @property
    def devtools_port(self):
        """Chromium's DevTools port."""
        return self.browser.port

    @property
    def browser_path(self):
        """The path of Chromium's browser websocket."""
        return self.browser.path


class Pool:
    """Every open session, at most `cap` per vendor. A session with no DevTools client for
    `idle` seconds is closed by `reap`."""

    def __init__(self, launch=Chromium, *, cap=CAP, idle=IDLE_SECONDS, clock=time.monotonic):
        self.launch, self.cap, self.idle, self.clock = launch, cap, idle, clock
        self._sessions = {}
        self._lock = threading.Lock()

    def open(self, vendor):
        """A new session, or None when the vendor already has `cap` open. Raises OSError
        when the browser does not start."""
        with self._lock:
            if sum(s.vendor == vendor for s in self._sessions.values()) >= self.cap:
                return None
            taken = {s.address for s in self._sessions.values()}
            address = next(a for a in ADDRESSES if a not in taken)
            session = Session(uuid.uuid4().hex[:16], vendor, address, None, self.clock(),
                              self.clock())
            self._sessions[session.id] = session  # holds the address while Chromium starts
        try:
            session.browser = self.launch(address)
        except OSError:
            with self._lock:
                self._sessions.pop(session.id, None)
            raise
        return session

    def get(self, vendor, session_id):
        """The vendor's open session with this id, or None."""
        with self._lock:
            session = self._sessions.get(session_id)
        return session if session and session.vendor == vendor and session.browser else None

    def close(self, vendor, session_id):
        """End a session; whether it was open."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or session.vendor != vendor or not session.browser:
                return False
            del self._sessions[session_id]
        session.browser.close()
        return True

    def close_all(self):
        """End every session."""
        with self._lock:
            sessions = [s for s in self._sessions.values() if s.browser]
            for session in sessions:
                del self._sessions[session.id]
        for session in sessions:
            session.browser.close()

    def reap(self):
        """End every session that has had no DevTools client for `idle` seconds."""
        now = self.clock()
        with self._lock:
            idle = [s for s in self._sessions.values()
                    if s.browser and not s.clients and now - s.idle_since > self.idle]
        for session in idle:
            self.close(session.vendor, session.id)

    def session_for_address(self, address):
        """The open session whose Chromium loads pages from `address`, or None."""
        with self._lock:
            return next((s for s in self._sessions.values()
                         if s.address == address and s.browser), None)

    def attach(self, session, delta):
        """Count a DevTools client connecting (+1) or leaving (-1)."""
        with self._lock:
            session.clients += delta
            if not session.clients:
                session.idle_since = self.clock()


def relay(pool, session, client, head, buffered):
    """Pass a DevTools websocket through to the session's Chromium, byte for byte, until
    either side closes. `head` is the client's request head with its path and Host already
    rewritten for Chromium; `buffered` is what the client sent after it."""
    upstream = socket.create_connection(("127.0.0.1", session.devtools_port), timeout=10)
    upstream.settimeout(None)
    pool.attach(session, 1)
    try:
        upstream.sendall(head + buffered)
        sockets = [client, upstream]
        while True:
            readable, _, _ = select.select(sockets, [], [], 1.0)
            if pool.get(session.vendor, session.id) is None:
                return
            for source in readable:
                data = source.recv(65536)
                if not data:
                    return
                (upstream if source is client else client).sendall(data)
    except OSError:
        return
    finally:
        pool.attach(session, -1)
        upstream.close()
