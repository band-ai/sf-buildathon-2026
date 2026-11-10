"""The mock's mutable state, and the admin API that controls it during a test run."""
import hmac
import json
import threading
import time
from collections import Counter

from .browsers import Pool
from .log import Log
from .search import draw

PROVIDERS = ("nimble", "tavily", "kernel", "browserbase")
METHODS = ("search", "extract", "research", "session", "browse")
FAULTS = {"error": 500, "rate_limit": 429, "none": None}
DELAY = "delay"
THROTTLE = "throttle"
MAX_DELAY = 10
REPEAT_SECONDS = 1.0  # stage-2.md, Rate limits: the same call this soon after a 429 gets 429
MAX_IN_A_ROW = 3      # and no call gets more than three 429s in a row


def error(status, message):
    """The JSON error body every provider answers with; tavily-python reads `detail`."""
    return {"error": {"code": str(status), "message": message}, "detail": {"error": message}}


def fingerprint(provider, method, request):
    """What makes two calls the same call: the provider, the operation and the request body
    as canonical JSON. Each (provider, method) the mock faults is one verb and path, and no
    such path carries arguments, so the body holds all of them."""
    return provider, method, json.dumps(request, sort_keys=True, separators=(",", ":"))


class State:  # pylint: disable=too-many-instance-attributes
    """The corpus, current epoch, injected faults, weather, call log, research runs and
    browser sessions."""

    def __init__(self, corpus, token, browsers=None, clock=time.monotonic):
        self.corpus = corpus
        self.token = token
        self.browsers = browsers or Pool()
        self.clock = clock
        self.log = Log()
        self.epoch = 0
        self.weather = False
        self._faults = {}
        self._counts = Counter()
        self._refused = {}  # fingerprint -> (429s in a row, clock time of the last)
        self._runs = {}
        self._lock = threading.Lock()

    def reset(self, epoch):
        """Clear the log, every fault, the weather, the call counts and the 429s given, end
        every browser session, and set the epoch."""
        with self._lock:
            self.epoch = epoch
            self.weather = False
            self._faults.clear()
            self._counts.clear()
            self._refused.clear()
        self.browsers.close_all()
        self.log.clear()

    def set_faults(self, provider, methods, fault):
        """From now on answer these methods with `fault`: an error status, `(DELAY, seconds)`
        to answer normally after a pause, or a set (THROTTLE) that collects the fingerprints
        it has turned away once. None clears the fault."""
        with self._lock:
            for method in methods:
                self._faults[provider, method] = fault

    def add_run(self, provider, run):
        """Keep a new research run and return its id, unique for the server's lifetime."""
        with self._lock:
            run_id = f"run-{len(self._runs) + 1}"
            self._runs[provider, run_id] = run
        return run_id

    def run(self, provider, run_id):
        """A research run this provider created, or None."""
        with self._lock:
            return self._runs.get((provider, run_id))

    def rate_limited(self, provider, number):
        """Whether the weather turns away a provider's `number`-th call since the reset."""
        traits = self.corpus.traits
        rate = traits["providers"].get(provider, {}).get("rate_limit", 0)
        return draw(traits["seed"], provider, number) < rate

    def fault_for(self, key, provider, method):
        """What answers the call `key` instead of the provider: 429 when the same call was
        answered 429 less than REPEAT_SECONDS ago; else the method's fault, a throttle
        being 429 the first time it sees the call and None after; else, with no fault set,
        429 when the weather turns the call away. Never 429 a (MAX_IN_A_ROW + 1)-th time in
        a row."""
        with self._lock:
            scripted = self._faults.get((provider, method))
            self._counts[provider] += 1
            number = self._counts[provider]
            in_a_row, last = self._refused.get(key, (0, None))
            repeated = last is not None and self.clock() - last < REPEAT_SECONDS
            fault = scripted
            if isinstance(scripted, set):
                fault = None if key in scripted else FAULTS["rate_limit"]
                scripted.add(key)
        if scripted is None and self.weather and self.rate_limited(provider, number):
            fault = FAULTS["rate_limit"]
        if repeated:
            fault = FAULTS["rate_limit"]
        return None if fault == FAULTS["rate_limit"] and in_a_row >= MAX_IN_A_ROW else fault

    def call(self, provider, method, request, answer, **entry):
        """Answer and log one billable call, unless a fault (`fault_for`) answers it first
        with 500 or 429, at cost 0. `request` is the request body.

        `answer()` returns `(status, payload, cost, served)`, and may add a dict of further
        log fields; `entry` holds the log entry's `depth`, `query`, `max_results`, `fields`,
        `urls` and `session`.
        """
        key = fingerprint(provider, method, request)
        fault = self.fault_for(key, provider, method)
        if fault in (FAULTS["error"], FAULTS["rate_limit"]):
            status, payload = fault, error(fault, "injected fault")
            self.log.record(provider, method, cost=0, status=status, **entry)
        else:
            if isinstance(fault, tuple):
                time.sleep(fault[1])
            status, payload, cost, served, *more = answer()
            self.log.record(provider, method, cost=cost, status=status, served=served,
                            **entry, **(more[0] if more else {}))
        with self._lock:
            if status == 429:
                self._refused[key] = (self._refused.get(key, (0, None))[0] + 1, self.clock())
            else:
                self._refused.pop(key, None)
        return status, payload

    def open_session(self, vendor, request, cost, describe):
        """Open and log a browser session: `describe(session)` is the vendor's payload. At
        the vendor's session cap the answer is 429, and a browser that does not start is
        500; neither costs anything."""
        def answer():
            try:
                session = self.browsers.open(vendor)
            except OSError:
                return 500, error(500, "the browser did not start"), 0, []
            if session is None:
                return 429, error(429, "too many open sessions"), 0, []
            return 200, describe(session), cost, [], {"session": session.id}

        return self.call(vendor, "session", request, answer)


def route(state, verb, path, token, body):
    """Answer an admin request as `(status, payload)`, or None for a 404."""
    if (verb, path) == ("GET", "/health"):
        return 200, {"status": "ok"}
    if not state.token or not hmac.compare_digest((token or "").encode(), state.token.encode()):
        return None
    handler = ROUTES.get((verb, path))
    return handler(state, body) if handler else None


def calls(state, _body):
    """Every provider call since the last reset."""
    return 200, {"calls": state.log.calls()}


def epoch_of(value):
    """The epoch a request names, or None when it is not a non-negative integer."""
    valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0
    return value if valid else None


def reset(state, body):
    """Clear the log, faults and weather and set the epoch, 0 by default."""
    epoch = epoch_of(body.get("epoch", 0))
    if epoch is None:
        return 400, error(400, "epoch must be a non-negative integer")
    state.reset(epoch)
    return 204, None


def set_epoch(state, body):
    """Serve another epoch from now on."""
    epoch = epoch_of(body.get("epoch"))
    if epoch is None:
        return 400, error(400, "epoch must be a non-negative integer")
    state.epoch = epoch
    return 204, None


def set_weather(state, body):
    """Turn the weather, the traits' seeded rate limits, on or off."""
    if not isinstance(body.get("on"), bool):
        return 400, error(400, "on must be true or false")
    state.weather = body["on"]
    return 204, None


def delay_of(value):
    """The seconds a delay fault names, or None unless a number in (0, MAX_DELAY]."""
    valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    return value if valid and 0 < value <= MAX_DELAY else None


def faults(state, body):
    """Answer a provider's methods with 500 or 429, with 429 the first time each call is
    made, or after a delay, from now on; or stop."""
    methods, mode = body.get("methods"), body.get("mode")
    if (body.get("provider") not in PROVIDERS or mode not in (*FAULTS, DELAY, THROTTLE)
            or not isinstance(methods, list) or not set(methods) <= set(METHODS)):
        return 400, error(400, "provider, methods or mode is not recognised")
    if mode == DELAY:
        seconds = delay_of(body.get("seconds"))
        if seconds is None:
            return 400, error(400, f"a delay needs seconds in (0, {MAX_DELAY}]")
        fault = (DELAY, seconds)
    elif mode == THROTTLE:
        fault = set()
    else:
        fault = FAULTS[mode]
    state.set_faults(body["provider"], methods, fault)
    return 204, None


ROUTES = {("GET", "/log"): calls, ("POST", "/reset"): reset, ("POST", "/epoch"): set_epoch,
          ("POST", "/faults"): faults, ("POST", "/weather"): set_weather}
