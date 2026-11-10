"""Stage 2 sample — the shipped smoke checks.

A sample, not the graded suite: one happy path across each surface so a service can be
wired against it. The spec is the contract and the graded checks are the spec's. Passing
everything here means the wiring is right, not that the stage holds.
"""
# pylint: disable=missing-function-docstring,unused-argument,too-many-arguments
# pylint: disable=too-many-positional-arguments
import httpx
import pytest
from playwright.sync_api import expect

import fixtures as fx
import screens
from harness.http import assert_status

pytestmark = pytest.mark.stage(2)


def disputed(corpus, domains):
    """The first (domain, field) whose evidence supports two or more values."""
    return next((domain, name) for domain in domains for name in fx.FIELDS
                if len(corpus.expected(domain, name, stage=1)) > 1)


@pytest.mark.parametrize("route,anchor,signed", [
    ("/", "research-domain", True),
    ("/dossiers/{domain}", "dossier-domain", True),
    ("/dossiers/{domain}/evidence", "evidence-legal_name", True),
    ("/contested", "contested-list|empty-contested", True),
    ("/signup", "signup-submit", False),
    ("/login", "login-submit", False),
], ids=["list", "dossier", "evidence", "contested", "signup", "login"])
def test_routes_are_directly_navigable(world, build, plain, page, route, anchor, signed):
    build(plain[0])
    if signed:
        screens.sign_in(page)
    page.goto(route.format(domain=plain[0]))
    found = page.locator(", ".join(f"[data-testid='{name}']" for name in anchor.split("|")))
    expect(found.first).to_be_attached()


def test_every_field_has_ranked_candidates(world, build, plain, assert_citations):
    body = build(plain[0])
    assert body["state"] == "ready"
    assert_citations(body)
    for name in fx.FIELDS:
        field = body["fields"][name]
        fx.assert_candidates(name, field)
        for cand in field["candidates"]:
            assert fx.instant(cand["retrieved_at"]) == fx.instant(body["researched_at"]), cand


def test_agreed_fields_are_known(world, build, plain, corpus):
    body = build(plain[0])
    for name in fx.FIELDS:
        if len(corpus.expected(plain[0], name, stage=1)) == 1:
            field = body["fields"][name]
            assert field["value"] in corpus.expected(plain[0], name, stage=2), (name, field)
            assert field["status"] == ("unknown" if field["value"] is None else "known"), field


def test_disagreeing_sources_make_a_field_contested(world, build, plain, corpus):
    domain, name = disputed(corpus, plain)
    field = build(domain)["fields"][name]
    values = corpus.expected(domain, name, stage=1)
    assert field["status"] == "contested" and field["value"] in values, field
    assert {c["value"] for c in field["candidates"]} == values, field["candidates"]
    assert field["citations"], field


def test_api_and_browser_share_the_dossier_route(world, build, plain, base_url):
    build(plain[0])
    url = f"{base_url}/dossiers/{plain[0]}"
    auth = {"Authorization": f"Bearer {world.alice.token}"}
    html = httpx.get(url, headers={**auth, "Accept": "text/html"}, follow_redirects=True)
    assert html.status_code == 200, html.status_code
    assert html.headers["content-type"].startswith("text/html"), html.headers
    api = assert_status(httpx.get(url, headers=auth), 200).json()
    assert api["domain"] == plain[0]


def test_dossier_screen_shows_its_fields(world, build, plain, page):
    body = build(plain[0])
    screens.sign_in(page)
    screens.open_dossier(page, plain[0])
    expect(page.get_by_test_id("dossier-domain")).to_have_text(plain[0])
    for name in fx.FIELDS:
        field = body["fields"][name]
        expect(page.get_by_test_id(f"field-{name}")).to_have_attribute(
            "data-status", field["status"])
        if field["value"] is not None:
            expect(page.get_by_test_id(f"field-value-{name}")).to_have_attribute(
                "data-value", str(field["value"]))


def test_research_from_the_list_opens_the_dossier(world, settle, plain, page):
    screens.sign_in(page)
    page.goto("/")
    page.get_by_test_id("research-domain").fill(f"WWW.{plain[0].upper()}")
    page.get_by_test_id("research-submit").click()
    page.wait_for_url(f"**/dossiers/{plain[0]}")
    expect(page.get_by_test_id("dossier-domain")).to_have_text(plain[0])
    assert settle(plain[0])["state"] == "ready"
