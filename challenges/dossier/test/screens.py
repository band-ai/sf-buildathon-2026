"""Browser helpers for the stage-2 screens. Elements are found by `data-testid` only."""
from __future__ import annotations

import re

from playwright.sync_api import expect

import fixtures as fx


def sign_in(page, user: dict | None = None) -> None:
    """Sign in through `/login`, as Alice unless `user` is given, and wait for
    `current-user`."""
    user = user or fx.ALICE
    page.goto("/login")
    page.get_by_test_id("login-email").fill(user["email"])
    page.get_by_test_id("login-password").fill(user["password"])
    page.get_by_test_id("login-submit").click()
    expect(page.get_by_test_id("current-user")).to_be_visible()


def open_dossier(page, domain: str, state: str = "ready") -> None:
    """Go to `/dossiers/{domain}` and wait until it shows `state`."""
    page.goto(f"/dossiers/{domain}")
    expect(page.get_by_test_id("dossier-state")).to_have_text(state)


def testids(page, pattern: str) -> list[str]:
    """The `data-testid`s that fully match `pattern`, in document order."""
    found = page.eval_on_selector_all(
        "[data-testid]", "els => els.map(e => e.getAttribute('data-testid'))")
    return [name for name in found if re.fullmatch(pattern, name)]


def links_to(locator, path: str) -> bool:
    """Whether a link the element is, sits in, or contains goes to `path`."""
    return locator.evaluate(
        "(el, path) => [el.closest('a[href]'), ...el.querySelectorAll('a[href]')].some("
        "a => a && new URL(a.getAttribute('href'), location.href).pathname === path)", path)


def has_link_to(locator, url: str) -> bool:
    """Whether the element is, or contains, a link whose `href` is exactly `url`."""
    return locator.evaluate(
        "(el, url) => [el, ...el.querySelectorAll('a')].some("
        "a => a.tagName === 'A' && a.getAttribute('href') === url)", url)


def text(locator) -> str:
    """The element's text with each run of whitespace written as one space."""
    return " ".join(locator.text_content().split())
