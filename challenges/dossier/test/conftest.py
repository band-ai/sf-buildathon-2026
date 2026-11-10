"""Track-level pytest configuration for `dossier`.

Options the harness passes (registered in `harness/plugin.py`) include `--web-url`,
`--web-admin-token` and `--web-corpus` (the mock web), and `--control-dir` (where a restart
check asks the harness to restart the service).
"""
# pylint: disable=wrong-import-position
from __future__ import annotations

import functools
import pathlib
import sys
import time
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import fixtures as fx  # noqa: E402
import web as dossier_web  # noqa: E402
from harness import control  # noqa: E402
from harness.http import RESET_TIMEOUT, assert_status, new_key  # noqa: E402
from harness.mockweb import corpus_dir  # noqa: E402

BUILD_SECONDS, SETTLE_SECONDS = fx.BUILD_SECONDS, fx.SETTLE_SECONDS
POLL_SECONDS = 0.1
HEALTH_SECONDS = 60  # stage 1 §3.2: /health answers within 60 s of container start


def option(request, name: str) -> str:
    """A required command-line option, or a clear failure."""
    value = request.config.getoption(name)
    if not value:
        pytest.fail(f"{name} is required (or run through `python -m harness run`)")
    return value


@functools.cache
def load_corpus(path: str, key: str | None) -> dossier_web.Corpus:
    """A corpus set with its key, read once per session."""
    return dossier_web.Corpus(path, key=key)


def pytest_configure(config):
    """Register the `plants` marker."""
    config.addinivalue_line(
        "markers", "plants(*kinds, where=None, fields=None): run once per planted (domain, "
        "field) of these kinds, as `rendered@sole` with a scope, on one of `fields` (default "
        "the six), for which where(corpus, domain, field) holds")


def pytest_generate_tests(metafunc):
    """A check marked `plants(...)` takes `plant`, one (domain, field) per plant of those
    kinds in the corpus the run serves (`--web-corpus`, else the one the harness would
    serve) on one of the marker's `fields` (default the six; a title such as `cfo` for
    `executives`) for which its `where(corpus, domain, field)`, if given, holds, so a
    service that misses a trap fails once per planted instance."""
    marker = metafunc.definition.get_closest_marker("plants")
    if marker is None:
        return
    config = metafunc.config
    served = load_corpus(config.getoption("--web-corpus") or str(corpus_dir("dossier")),
                         config.getoption("--web-key"))
    where = marker.kwargs.get("where", lambda *_: True)
    names = marker.kwargs.get("fields", dossier_web.FIELDS)
    found = sorted({plant for spec in marker.args
                    for kind, _, scope in [spec.partition("@")]
                    for plant in served.planted(kind, scope or None, names)
                    if where(served, *plant)})
    metafunc.parametrize("plant", found, ids=[f"{domain}-{name}" for domain, name in found])


@pytest.fixture
def web(request):
    """The mock web's admin API."""
    return dossier_web.Web(option(request, "--web-url"), option(request, "--web-admin-token"))


@pytest.fixture(scope="session")
def corpus(request):
    """The corpus the mock serves, with its key."""
    return load_corpus(option(request, "--web-corpus"), request.config.getoption("--web-key"))


@pytest.fixture
def plain(corpus):  # pylint: disable=redefined-outer-name
    """The companies the corpus key tags `plain`, sorted by domain."""
    domains = corpus.plain()
    assert len(domains) >= 3, f"{corpus.path}: fewer than three plain companies"
    return domains


@pytest.fixture
def assert_citations(corpus):  # pylint: disable=redefined-outer-name
    """`assert_citations(body)`: raises FabricationError for an invented citation."""
    return functools.partial(dossier_web.assert_citations, corpus=corpus)


@pytest.fixture
def clock(base_url):
    """`clock(now)`: POST /_test/clock, unauthenticated. Returns the response."""
    def _clock(now: str) -> httpx.Response:
        return httpx.post(f"{base_url}/_test/clock", json={"now": now}, timeout=RESET_TIMEOUT)
    return _clock


@pytest.fixture
def restart(request, base_url):
    """`restart()`: have the harness kill the service's container (SIGKILL) and start it
    again, then wait until `GET /health` answers 200. A client made before it may hold a
    connection to the killed process, so a check reads through new ones afterwards."""
    control_dir = option(request, "--control-dir")

    def _restart() -> None:
        control.request(control_dir)
        deadline = time.monotonic() + HEALTH_SECONDS
        while True:
            try:
                if httpx.get(f"{base_url}/health", timeout=5).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            assert time.monotonic() < deadline, f"no /health {HEALTH_SECONDS}s after a restart"
            time.sleep(POLL_SECONDS)
    return _restart


def drain(client) -> None:
    """Best effort: wait for builds a check left running, so that their provider calls do not
    land in the next check's call log. Never fails the check."""
    deadline = time.monotonic() + SETTLE_SECONDS
    while time.monotonic() < deadline:
        try:
            resp = client.get("/dossiers", params={"limit": 200})
            if resp.status_code != 200 or all(
                    d["state"] != "building" for d in resp.json()["dossiers"]):
                return
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return
        time.sleep(POLL_SECONDS)


@pytest.fixture
def world(reset, api, web):  # pylint: disable=redefined-outer-name
    """A reset service and mock (epoch 0), with Alice and Bob signed in. At teardown it waits
    for any build still running."""
    fixture = fx.fixture()
    reset(fixture)
    web.reset()
    namespace = SimpleNamespace(
        fixture=fixture,
        alice=api().authenticate(fx.ALICE["email"], fx.ALICE["password"]),
        bob=api().authenticate(fx.BOB["email"], fx.BOB["password"]))
    yield namespace
    drain(namespace.alice)


@pytest.fixture
def settle(world):  # pylint: disable=redefined-outer-name
    """Wait until a dossier's build has ended (`ready` or `failed`), for at most `seconds`.
    A check whose subject is the build time bound passes `BUILD_SECONDS`. Returns its body."""
    def _settle(domain: str, client=None, seconds: float = SETTLE_SECONDS) -> dict:
        client = client or world.alice
        deadline = time.monotonic() + seconds
        while True:
            body = assert_status(client.get(f"/dossiers/{domain}"), 200).json()
            if body["state"] in ("ready", "failed"):
                return body
            assert time.monotonic() < deadline, \
                f"{domain} still {body['state']} after {seconds}s"
            time.sleep(POLL_SECONDS)
    return _settle


@pytest.fixture
def build(world, settle):  # pylint: disable=redefined-outer-name
    """Request a dossier and wait until it is `ready` or `failed`, for at most `seconds`.
    Returns its body."""
    def _build(domain: str, client=None, seconds: float = SETTLE_SECONDS) -> dict:
        client = client or world.alice
        assert_status(client.post("/dossiers", json={"domain": domain},
                                  idempotency_key=new_key()), 202)
        return settle(domain, client, seconds)
    return _build


@pytest.fixture
def build_all(world, settle):  # pylint: disable=redefined-outer-name
    """Request several fresh dossiers at once, then wait for each. Returns {domain: body}."""
    def _build_all(domains) -> dict:
        for domain in domains:
            assert_status(world.alice.post("/dossiers", json={"domain": domain},
                                           idempotency_key=new_key()), 202)
        return {domain: settle(domain) for domain in domains}
    return _build_all


@pytest.fixture
def refresh(world, settle):  # pylint: disable=redefined-outer-name
    """Stage 3: refresh a dossier and wait until its build has ended. Returns its body."""
    def _refresh(domain: str, client=None) -> dict:
        client = client or world.alice
        assert_status(client.post(f"/dossiers/{domain}/refresh", idempotency_key=new_key()),
                      202)
        return settle(domain, client)
    return _refresh


@pytest.fixture
def refresh_all(world, settle):  # pylint: disable=redefined-outer-name
    """Stage 3: refresh several dossiers at once, then wait for each. Returns {domain: body}."""
    def _refresh_all(domains) -> dict:
        for domain in domains:
            assert_status(world.alice.post(f"/dossiers/{domain}/refresh",
                                           idempotency_key=new_key()), 202)
        return {domain: settle(domain) for domain in domains}
    return _refresh_all


@pytest.fixture
def finish_batch(world):  # pylint: disable=redefined-outer-name
    """Stage 4: poll a batch until it is `done`, for at most SETTLE_SECONDS. Returns
    its last body, done or not, so a caller can record what it saw before asserting."""
    def _finish(batch_id: str, client=None) -> dict:
        client = client or world.alice
        deadline = time.monotonic() + SETTLE_SECONDS
        while True:
            body = assert_status(client.get(f"/batches/{batch_id}"), 200).json()
            if body["state"] == "done" or time.monotonic() >= deadline:
                return body
            time.sleep(POLL_SECONDS)
    return _finish


@pytest.fixture
def run_batch(world, finish_batch):  # pylint: disable=redefined-outer-name
    """Stage 4: POST /batches and wait until the batch is `done`. Returns (the 202 body, the
    finished body)."""
    def _run(domains, budget_units: int, client=None) -> tuple:
        client = client or world.alice
        created = assert_status(client.post("/batches", json={
            "domains": list(domains), "budget_units": budget_units},
            idempotency_key=new_key()), 202).json()
        done = finish_batch(created["batch_id"], client)
        assert done["state"] == "done", f"batch still {done['state']} after {SETTLE_SECONDS}s"
        return created, done
    return _run
