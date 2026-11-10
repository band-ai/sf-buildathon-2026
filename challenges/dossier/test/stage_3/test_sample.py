"""Stage 3 sample — the shipped smoke checks.

A sample, not the graded suite: one happy path across each surface so a service can be
wired against it. The spec is the contract and the graded checks are the spec's. Passing
everything here means the wiring is right, not that the stage holds.
"""
# pylint: disable=missing-function-docstring,unused-argument,too-many-arguments
# pylint: disable=too-many-positional-arguments,too-many-locals
import pytest

import fixtures as fx
from harness.http import assert_error, assert_status

pytestmark = pytest.mark.stage(3)

MIDDLE, LATER = fx.MIDDLE, fx.LATER


def moving(corpus, domains):
    """The first company whose expected values differ between epochs, with those fields."""
    return next((domain, sorted(corpus.moved(domain), key=fx.FIELDS.index))
                for domain in domains if corpus.moved(domain))


def later(web, clock):
    """The web moves to epoch 1 and the clock to LATER."""
    web.epoch(1)
    assert_status(clock(LATER), 204)


def test_first_build_writes_initial_history(world, build, plain):
    body = build(plain[0])
    history = assert_status(world.alice.get(f"/dossiers/{plain[0]}/history"), 200).json()
    assert history["domain"] == plain[0]
    fx.assert_field_set(history["fields"], 3)
    for name in fx.FIELDS:
        field, entries = body["fields"][name], history["fields"][name]
        if field["value"] is None:
            assert entries == [], (name, entries)
            continue
        assert len(entries) == 1 and entries[0]["type"] == "initial", (name, entries)
        assert fx.same_value(entries[0]["value"], field["value"]), (name, entries)
        assert fx.instant(entries[0]["learned_at"]) == fx.instant(body["researched_at"])


def test_first_build_names_the_executives(world, build, plain, corpus, assert_citations):
    field = build(plain[0])["fields"]["executives"]
    assert fx.matches(field["value"], corpus.expected(plain[0], "executives", stage=3)), field
    assert_citations({"fields": {"executives": field}})


def test_first_build_adds_nothing_to_the_feed(world, build, plain):
    build(plain[0])
    feed = assert_status(world.alice.get("/changes"), 200).json()
    assert feed == {"changes": [], "has_more": False}, feed


def test_a_refresh_that_changes_a_value_adds_feed_entries(world, web, clock, build, refresh,
                                                          plain, corpus):
    domain, names = moving(corpus, plain)
    before = build(domain)
    later(web, clock)
    after = refresh(domain)
    feed = assert_status(world.alice.get("/changes"), 200).json()
    assert [(c["domain"], c["field"], c["type"]) for c in feed["changes"]] == \
        [(domain, name, "change") for name in names], feed
    for entry, name in zip(feed["changes"], names):
        assert entry["from"] == before["fields"][name]["value"], entry
        assert entry["to"] == after["fields"][name]["value"], entry
        assert entry["to"] in corpus.expected(domain, name, stage=3, epoch=1), entry
        assert fx.instant(entry["learned_at"]) == fx.instant(LATER), entry


def test_as_of_answers_as_the_service_had_it(world, web, clock, build, refresh, plain,
                                             corpus):
    domain, names = moving(corpus, plain)
    before = build(domain)
    later(web, clock)
    refresh(domain)
    then = assert_status(world.alice.get(f"/dossiers/{domain}", params={"as_of": MIDDLE}),
                         200).json()
    assert then["state"] == "ready"
    assert fx.instant(then["researched_at"]) == fx.instant(before["researched_at"])
    for name in names:
        assert then["fields"][name]["value"] == before["fields"][name]["value"], name
        assert then["fields"][name]["learned_at"] == before["fields"][name]["learned_at"], name
        assert then["fields"][name]["true_from"] == before["fields"][name]["true_from"], name


def test_as_of_before_the_first_build_is_not_found(world, build, plain):
    build(plain[0])
    assert_error(world.alice.get(f"/dossiers/{plain[0]}",
                                 params={"as_of": "2026-02-01T00:00:00+00:00"}),
                 404, "not_found")


def test_as_of_without_an_offset_is_rejected(world, build, plain):
    build(plain[0])
    assert_error(world.alice.get(f"/dossiers/{plain[0]}", params={"as_of": "2026-03-02T09:00:00"}),
                 422, "validation_failed")


def test_values_at_a_date_have_the_dossier_shape(world, build, plain):
    build(plain[0])
    day = fx.NOW[:10]
    body = assert_status(world.alice.get(f"/dossiers/{plain[0]}/values",
                                         params={"true_at": day}), 200).json()
    assert (body["domain"], body["true_at"]) == (plain[0], day), body
    fx.assert_field_set(body["fields"], 3)
    for name, field in body["fields"].items():
        assert set(field) >= {"value", "true_from", "citations"}, (name, field)


def test_values_need_a_date(world, build, plain):
    build(plain[0])
    assert_error(world.alice.get(f"/dossiers/{plain[0]}/values"), 422, "validation_failed")
