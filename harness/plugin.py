"""Pytest plugin shared by both tracks.

A track's `test/conftest.py` enables it with:

    pytest_plugins = ["harness.plugin"]

It supplies the base URL, a client factory, and `reset` -- the fixture loader that
every test calls before it asserts anything.
"""
from __future__ import annotations

import json
import pathlib
from urllib.parse import urlsplit

import httpx
import pytest

from harness.http import Api, RESET_TIMEOUT, assert_status


def pytest_addoption(parser):
    """Register the harness command-line options."""
    group = parser.getgroup("dark factory harness")
    group.addoption("--base-url", action="store", default=None,
                    help="Base URL of the service under test, e.g. http://127.0.0.1:8080")
    group.addoption("--previous-base-url", default=None,
                    help="preceding stage's service, used to produce upgrade snapshots")
    group.addoption('--implementation-stage', choices=('1', '2', '3', '4'), default=None,
                    help='stage implemented by the service, including for cumulative suites')


    group.addoption("--web-url", default=None,
                    help="admin base URL of the mock web (Dossier track)")
    group.addoption("--web-admin-token", default=None,
                    help="X-Mock-Admin token of the mock web (Dossier track)")
    group.addoption("--web-corpus", default=None,
                    help="folder of the corpus the mock web serves (Dossier track)")
    group.addoption("--web-key", default=None,
                    help="the corpus's key file, if not its own key.json (Dossier track)")
    group.addoption("--questions-url", default=None,
                    help="base URL of the mock question API (Forecast track)")
    group.addoption("--questions-admin-token", default=None,
                    help="X-Questions-Admin token of the mock question API (Forecast track)")
    group.addoption("--control-dir", default=None,
                    help="folder where checks ask the harness to restart the service")
    group.addoption("--harness-summary", default=None, help="write check counts as JSON")


_COUNTS = {}
_PASSED = {}   # node id -> whether that check passed; filtered-out checks did not


def pytest_configure(config):
    """Reset the counters and register the stage marker."""
    _COUNTS.clear()
    _PASSED.clear()
    _COUNTS.update(collected=0, passed=0, failed=0, errors=0, skipped=0, deselected=0,
                   xfailed=0, leaks=0, fabrications=0, economy=None)
    config.addinivalue_line("markers", "stage(n): the stage this test belongs to")
    config.addinivalue_line(
        "markers", "leak: an attack whose failure is a cross-tenant leak")


def pytest_deselected(items):
    """Count deselected checks as not passed."""
    _COUNTS["deselected"] += len(items)
    _PASSED.update((item.nodeid, False) for item in items)


def pytest_collection_finish(session):
    """Record every collected check, starting as not passed."""
    _COUNTS["collected"] = len(session.items) + _COUNTS["deselected"]
    for item in session.items:
        _PASSED.setdefault(item.nodeid, False)


def pytest_collectreport(report):
    """Count collection errors and skips."""
    if report.failed:
        _COUNTS["errors"] += 1
    elif report.skipped:
        _COUNTS["skipped"] += 1


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # pylint: disable=unused-argument
    """Flag a failed call whose exception is a `FabricationError`, matched by class name
    so the plugin does not import challenge code."""
    report = (yield).get_result()
    if call.when == "call" and call.excinfo is not None:
        report.fabrication = any(cls.__name__ == "FabricationError"
                                 for cls in call.excinfo.type.__mro__)


def pytest_runtest_logreport(report):
    """Count each check's outcome and record whether it passed."""
    if getattr(report, "wasxfail", None):
        _COUNTS["xfailed"] += 1
    elif report.skipped:
        _COUNTS["skipped"] += 1
    elif report.failed:
        _COUNTS["failed" if report.when == "call" else "errors"] += 1
    elif report.when == "call" and report.passed:
        _COUNTS["passed"] += 1
    if report.when == "call" and report.failed and "leak" in report.keywords:
        _COUNTS["leaks"] += 1
    if report.failed and getattr(report, "fabrication", False):
        _COUNTS["fabrications"] += 1
    if report.when == "call":
        for name, value in report.user_properties:
            if name == "economy":
                _COUNTS["economy"] = value
    if report.failed or getattr(report, "wasxfail", None):
        _PASSED[report.nodeid] = False
    elif report.when == "call" and report.passed:
        _PASSED[report.nodeid] = True


def pytest_sessionfinish(session, exitstatus):  # pylint: disable=unused-argument
    """Write the check counts to --harness-summary, when given."""
    path = session.config.getoption("--harness-summary")
    if path:
        files = {}
        for nodeid, passed in _PASSED.items():
            result = files.setdefault(nodeid.split("::", 1)[0], {"passed": 0, "total": 0})
            result["total"] += 1
            result["passed"] += passed
        pathlib.Path(path).write_text(json.dumps({**_COUNTS, "files": files}) + "\n",
                                      encoding="utf-8")


@pytest.fixture(scope="session")
def base_url(request) -> str:
    """The --base-url of the service under test, without a trailing slash."""
    url = request.config.getoption("--base-url")
    if not url:
        pytest.fail("--base-url is required (or run through `python -m harness run`)")
    return url.rstrip("/")


@pytest.fixture
def implementation_stage(request) -> int:
    """The service's stage; direct pytest defaults to the test's stage marker."""
    stage = request.config.getoption('--implementation-stage')
    if stage is None:
        marker = request.node.get_closest_marker('stage')
        if marker is None:
            pytest.fail('this test has no stage(n) marker; pass --implementation-stage')
        stage = marker.args[0]
    return int(stage)


@pytest.fixture
def reset(base_url):  # pylint: disable=redefined-outer-name
    """POST /_test/reset with a fixture body. Returns the response.

    The spec requires this to be synchronous: when it returns 204 the next request
    must see the fixture and nothing else. Tests rely on that, so a non-204 here
    fails the test rather than being silently tolerated -- except when a test is
    deliberately checking a rejected fixture, which uses `raw=True`.
    """
    def _reset(fixture: dict, *, raw: bool = False) -> httpx.Response:
        resp = httpx.post(f"{base_url}/_test/reset", json=fixture, timeout=RESET_TIMEOUT)
        if not raw:
            assert_status(resp, 204)
        return resp
    return _reset


@pytest.fixture
def api(base_url):  # pylint: disable=redefined-outer-name
    """Factory for API clients. Every client made here is closed at teardown."""
    made: list[Api] = []

    def _api(token: str | None = None) -> Api:
        client = Api(base_url, token=token)
        made.append(client)
        return client

    yield _api
    for client in made:
        client.close()


@pytest.fixture
def anon(api):  # pylint: disable=redefined-outer-name
    """An unauthenticated client."""
    return api()


@pytest.fixture
def previous_api(request):
    """A client for the preceding stage's service, closed at teardown."""
    url = request.config.getoption('--previous-base-url')
    if not url:
        pytest.fail('upgrade checks require the preceding stage: use harness run --repo '
                    '--stage N, or supply --previous-base-url for development')
    with Api(url, timeout=RESET_TIMEOUT) as client:
        yield client


# ---- stage 2: the browser ------------------------------------------------

def browser_args(base_url: str) -> list[str]:  # pylint: disable=redefined-outer-name
    """Chromium flags that make the service's origin a secure context.

    Loopback is always one, so a host-mode run gets secure-only APIs such as
    crypto.randomUUID; graders reach the service by container name over plain HTTP.
    Treating that origin as secure too makes both runs see the same browser.
    """
    parts = urlsplit(base_url)
    return [f"--unsafely-treat-insecure-origin-as-secure={parts.scheme}://{parts.netloc}"]


@pytest.fixture(scope="session")
def browser(base_url):  # pylint: disable=redefined-outer-name
    """One headless Chromium for the whole stage-2 run.

    Full Chromium, not the default headless shell, which ignores `browser_args`.
    """
    from playwright import sync_api as playwright  # pylint: disable=import-outside-toplevel
    with playwright.sync_playwright() as driver:
        instance = driver.chromium.launch(channel="chromium", args=browser_args(base_url))
        yield instance
        instance.close()


@pytest.fixture
def page(browser, base_url):  # pylint: disable=redefined-outer-name
    """A fresh browser context per test, so no session leaks between them."""
    context = browser.new_context(base_url=base_url)
    context.set_default_timeout(30_000)
    tab = context.new_page()
    yield tab
    # A route handler still running (a held or retried request) must not answer into a
    # closing context: that error would surface in the next test's new_context.
    tab.unroute_all(behavior="ignoreErrors")
    context.close()


@pytest.fixture
def tid():
    """`data-testid` selector. The suites find elements by these and nothing else."""
    return lambda name: f"[data-testid='{name}']"
