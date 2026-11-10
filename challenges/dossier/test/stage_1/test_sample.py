"""Stage 1 sample — the shipped smoke checks.

A sample, not the graded suite: one happy path across each surface so a service can be
wired against it. The spec is the contract and the graded checks are the spec's. Passing
everything here means the wiring is right, not that the stage holds.
"""
# pylint: disable=missing-function-docstring,unused-argument,too-many-arguments
# pylint: disable=too-many-positional-arguments
import pytest

import fixtures as fx
from harness.http import assert_error, assert_status, new_key

pytestmark = pytest.mark.stage(1)


def test_health(anon):
    assert assert_status(anon.get("/health"), 200).json() == {"status": "ok"}


def test_signup_and_login(world, api):
    signed = assert_status(api().signup("dee@example.com", "correct horse", "Dee"),
                           201).json()
    assert signed["display_name"] == "Dee" and signed["token"] and signed["user_id"]
    logged = assert_status(api().login("dee@example.com", "correct horse"), 200).json()
    assert logged["user_id"] == signed["user_id"] and logged["display_name"] == "Dee"


def test_build_a_dossier(world, build, plain, corpus, assert_citations,
                         implementation_stage):
    domain = plain[0]
    body = build(domain)
    assert body["state"] == "ready" and body["domain"] == domain and body["dossier_id"]
    fx.assert_dossier(body, implementation_stage, fields_stage=1)
    assert_citations(body)
    for name in fx.FIELDS:
        assert body["fields"][name]["value"] in corpus.expected(domain, name, stage=1), name


def test_request_returns_202_building(world, plain):
    body = assert_status(world.alice.post("/dossiers", json={"domain": plain[0]},
                                          idempotency_key=new_key()), 202).json()
    assert body["domain"] == plain[0] and body["state"] == "building" and body["dossier_id"]


def test_existing_dossier_is_200(world, build, plain):
    first = build(plain[0])
    again = assert_status(world.bob.post("/dossiers", json={"domain": plain[0]},
                                         idempotency_key=new_key()), 200).json()
    assert (again["dossier_id"], again["domain"], again["state"]) == \
        (first["dossier_id"], plain[0], "ready")


def test_replay_is_200(world, plain):
    key = new_key()
    first = assert_status(world.alice.post("/dossiers", json={"domain": plain[0]},
                                           idempotency_key=key), 202).json()
    again = world.alice.post("/dossiers", json={"domain": plain[0]}, idempotency_key=key)
    assert assert_status(again, 200).json() == first


def test_read_by_another_spelling(world, build, plain):
    first = build(plain[0])
    body = assert_status(world.bob.get(f"/dossiers/WWW.{plain[0].upper()}"), 200).json()
    assert body["dossier_id"] == first["dossier_id"] and body["domain"] == plain[0]


def test_list_dossiers(world, build, plain):
    body = build(plain[0])
    listed = assert_status(world.alice.get("/dossiers"), 200).json()
    assert listed["has_more"] is False
    [entry] = listed["dossiers"]
    assert entry["state"] == "ready"
    fx.assert_list_entry(entry, body)


def test_refresh_starts_a_build(world, build, settle, plain):
    first = build(plain[0])
    body = assert_status(world.alice.post(f"/dossiers/{plain[0]}/refresh",
                                          idempotency_key=new_key()), 202).json()
    assert body == {"dossier_id": first["dossier_id"], "domain": plain[0], "state": "building"}
    assert settle(plain[0])["state"] == "ready"


def test_unknown_dossier_is_404(world, plain):
    assert_error(world.alice.get(f"/dossiers/{plain[0]}"), 404, "not_found")


def test_export_shape(world, anon):
    snapshot = assert_status(anon.get("/_test/export"), 200).json()
    assert snapshot["track"] == "dossier" and snapshot["format_version"] == 1
    assert isinstance(snapshot["state"], dict)
