"""Stage 4 sample — the shipped smoke checks.

A sample, not the graded suite: one happy path across each surface so a service can be
wired against it. The spec is the contract and the graded checks are the spec's. Passing
everything here means the wiring is right, not that the stage holds.
"""
# pylint: disable=missing-function-docstring,unused-argument,too-many-arguments
# pylint: disable=too-many-positional-arguments
import pytest

import fixtures as fx
from harness.http import assert_error, assert_status

pytestmark = pytest.mark.stage(4)


def test_fields_carry_origins(world, build, plain):
    body = build(plain[0])
    assert body["state"] == "ready", body
    for name, field in body["fields"].items():
        fx.assert_origins(name, field)


def test_fields_carry_corroborated_since(world, build, plain):
    body = build(plain[0])
    for name, field in body["fields"].items():
        assert "corroborated_since" in field, (name, field)
        if field["corroborated_since"] is not None:
            fx.instant(field["corroborated_since"])


def test_first_build_names_the_investors(world, build, plain, corpus, assert_citations):
    field = build(plain[0])["fields"]["investors"]
    assert fx.matches(field["value"], corpus.expected(plain[0], "investors", stage=4)), field
    assert_citations({"fields": {"investors": field}})


def test_candidate_origins_follow_lineage(world, build_all, plain, corpus):
    for domain, body in build_all(plain).items():
        for name, field in body["fields"].items():
            for cand in field["candidates"]:
                assert cand["origin"] == corpus.origin(cand["url"], domain), (domain, name, cand)


def test_a_batch_researches_its_companies(world, run_batch, plain, corpus):
    created, done = run_batch(plain[:2], 200)
    fx.assert_batch(created, plain[:2], 200)
    fx.assert_batch(done, plain[:2], 200)
    assert [d["state"] for d in done["dossiers"]] == ["ready", "ready"], done
    for domain in plain[:2]:
        body = assert_status(world.alice.get(f"/dossiers/{domain}"), 200).json()
        for name, field in body["fields"].items():
            assert field["value"] in corpus.expected(domain, name, stage=4), (domain, name)


def test_a_batch_stays_within_its_budget(world, web, run_batch, plain):
    _, done = run_batch(plain[:3], 40)
    assert web.units() <= done["spent_units"] <= 40, (done, web.units())


def test_a_batch_needs_an_idempotency_key(world, plain):
    assert_error(world.alice.post("/batches", json={"domains": plain[:1], "budget_units": 100}),
                 400, "missing_idempotency_key")


def test_an_empty_batch_is_rejected(world):
    assert_error(world.alice.post("/batches", json={"domains": [], "budget_units": 100},
                                  idempotency_key="empty"), 422, "validation_failed")


def test_another_users_batch_is_not_found(world, run_batch, plain):
    created, _ = run_batch(plain[:1], 100)
    assert_error(world.bob.get(f"/batches/{created['batch_id']}"), 404, "not_found")


def test_a_build_completes_when_one_provider_fails(world, web, build, plain, corpus):
    """Each optional provider failing every call, or Nimble failing its research runs."""
    cases = [(provider, ["search", "extract", "research"])
             for provider in fx.PROVIDERS if provider != "nimble"] + [("nimble", ["research"])]
    assert len(plain) >= len(cases), plain
    for (provider, methods), domain in zip(cases, plain):
        web.reset()
        web.fault(provider, methods, "error")
        body = build(domain)
        assert body["state"] == "ready", (provider, body)
        for name in corpus.gathered(domain, research=provider != "nimble"):
            assert body["fields"][name]["value"] is not None, (provider, name, body["fields"][name])
