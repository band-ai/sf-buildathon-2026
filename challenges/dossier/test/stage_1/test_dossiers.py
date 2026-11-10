"""Dossiers (§4, §7, §8): requesting one, reading it, listing them.

A domain is normalised before anything else, so every spelling names one dossier and an
invalid one is 422.
"""
# pylint: disable=missing-function-docstring,unused-argument,too-many-arguments
# pylint: disable=too-many-positional-arguments
import pytest

import fixtures as fx
from harness.http import assert_error, assert_status, new_key

pytestmark = pytest.mark.stage(1)

LONG_LABEL = "a" * 63
LONGEST = ".".join([LONG_LABEL] * 3 + ["b" * 61])          # 253 characters
INVALID = ["https://{d}", "{d}/about", "localhost", "www.test", "-{d}", "{d}..", "a..test",
           "acme_co.test", "a" * 64 + ".test", LONGEST + "b", "", "   ", "acme co.test"]
SPELLINGS = ["  {D}  ", "www.{d}", "{d}.", "WWW.{D}."]


def spell(template, domain):
    """`template` with `{d}` as the domain and `{D}` as the domain in upper case."""
    return template.format(d=domain, D=domain.upper())


def request(client, domain, key=None):
    """POST /dossiers for `domain` (a raw string, not normalised here)."""
    return client.post("/dossiers", json={"domain": domain},
                       idempotency_key=new_key() if key is None else key)


def fail_every_provider(web):
    """Make every provider answer every method with an error."""
    for provider in fx.PROVIDERS:
        web.fault(provider, list(fx.METHODS), "error")


# ---- requesting a dossier ------------------------------------------------

def test_new_domain_is_202_building(world, plain):
    body = assert_status(request(world.alice, plain[0]), 202).json()
    assert body["domain"] == plain[0] and body["state"] == "building"
    assert isinstance(body["dossier_id"], str) and 1 <= len(body["dossier_id"]) <= 64


def test_existing_domain_is_200_with_its_current_state(world, build, plain):
    first = build(plain[0])
    for client in (world.alice, world.bob):
        body = assert_status(request(client, plain[0]), 200).json()
        assert body["dossier_id"] == first["dossier_id"]
        assert body["domain"] == plain[0] and body["state"] == "ready"


@pytest.mark.parametrize("template", SPELLINGS)
def test_response_carries_the_normalised_domain(world, plain, template):
    body = assert_status(request(world.alice, spell(template, plain[0])), 202).json()
    assert body["domain"] == plain[0]


def test_every_spelling_names_one_dossier(world, plain):
    first = assert_status(request(world.alice, plain[0]), 202).json()
    for template in SPELLINGS:
        body = assert_status(request(world.bob, spell(template, plain[0])), 200).json()
        assert body["dossier_id"] == first["dossier_id"] and body["domain"] == plain[0]
    listed = assert_status(world.alice.get("/dossiers"), 200).json()["dossiers"]
    assert [d["domain"] for d in listed] == [plain[0]]


@pytest.mark.parametrize("template", INVALID)
def test_invalid_domain_is_422(world, plain, template):
    assert_error(request(world.alice, spell(template, plain[0])), 422, "validation_failed")


@pytest.mark.parametrize("domain", [LONG_LABEL + ".test", LONGEST, "x-1.y2.test"])
def test_longest_valid_domains_are_accepted(world, domain):
    assert assert_status(request(world.alice, domain), 202).json()["domain"] == domain


def test_domain_missing(world):
    assert_error(world.alice.post("/dossiers", json={}, idempotency_key=new_key()),
                 422, "validation_failed")


@pytest.mark.parametrize("domain", [5, ["a.test"], {"domain": "a.test"}])
def test_domain_of_the_wrong_type(world, domain):
    assert_error(request(world.alice, domain), 400, "malformed_request")


def test_unparseable_body(world):
    assert_error(world.alice.post("/dossiers", content="{not json", idempotency_key=new_key()),
                 400, "malformed_request")


def test_unknown_body_fields_are_ignored(world, plain):
    resp = world.alice.post("/dossiers", json={"domain": plain[0], "fields": ["ceo"]},
                            idempotency_key=new_key())
    assert assert_status(resp, 202).json()["domain"] == plain[0]


# ---- reading a dossier ---------------------------------------------------

def test_researched_at_is_the_time_of_the_request(world, build, plain):
    assert fx.instant(build(plain[0])["researched_at"]) == fx.instant(fx.NOW)


def test_every_user_sees_the_same_dossier(world, build, plain):
    body = build(plain[0])
    assert assert_status(world.bob.get(f"/dossiers/{plain[0]}"), 200).json() == body


@pytest.mark.parametrize("template", ["{D}", "www.{d}", "{d}."])
def test_read_by_any_spelling(world, build, plain, template):
    body = build(plain[0])
    assert assert_status(world.alice.get(f"/dossiers/{spell(template, plain[0])}"),
                         200).json() == body


def test_unknown_dossier_is_404(world, build, plain):
    build(plain[0])
    assert_error(world.alice.get(f"/dossiers/{plain[1]}"), 404, "not_found")


@pytest.mark.parametrize("domain", ["localhost", "acme_co.test", "-a.test"])
def test_invalid_domain_in_the_path_is_422(world, domain):
    assert_error(world.alice.get(f"/dossiers/{domain}"), 422, "validation_failed")


def test_build_with_no_provider_answering_fails(world, web, build, plain):
    fail_every_provider(web)
    body = build(plain[0])
    assert body["state"] == "failed" and body["researched_at"] is None
    assert body["spent_units"] == 0
    fx.assert_all_unknown(body)


# ---- listing -------------------------------------------------------------

def test_list_entry_shape(world, build, plain):
    body = build(plain[0])
    listed = assert_status(world.bob.get("/dossiers"), 200).json()
    assert listed["has_more"] is False
    [entry] = listed["dossiers"]
    assert entry["state"] == "ready"
    fx.assert_list_entry(entry, body)


def test_list_is_ordered_by_domain(world, plain):
    for domain in reversed(plain[:3]):
        assert_status(request(world.alice, domain), 202)
    listed = assert_status(world.alice.get("/dossiers"), 200).json()["dossiers"]
    assert [d["domain"] for d in listed] == sorted(plain[:3])


def test_failed_dossier_lists_a_null_legal_name(world, web, build, plain):
    fail_every_provider(web)
    build(plain[0])
    [entry] = assert_status(world.alice.get("/dossiers"), 200).json()["dossiers"]
    assert entry["state"] == "failed" and entry["legal_name"] is None
    assert entry["researched_at"] is None


def test_q_matches_the_domain_ignoring_case(world, plain):
    for domain in plain[:2]:
        assert_status(request(world.alice, domain), 202)
    part = plain[0].split(".")[0][1:].upper()
    listed = assert_status(world.alice.get("/dossiers", params={"q": part}), 200).json()
    assert plain[0] in [d["domain"] for d in listed["dossiers"]]
    assert all(part.lower() in d["domain"] or part.lower() in (d["legal_name"] or "").lower()
               for d in listed["dossiers"])


def test_q_matches_the_legal_name_ignoring_case(world, build, plain):
    name = build(plain[0])["fields"]["legal_name"]["value"]
    assert name, f"{plain[0]} has no legal name"
    words = [w for w in name.split() if w.lower().strip(".,") not in plain[0]]
    part = (words[-1] if words else name).swapcase()
    listed = assert_status(world.alice.get("/dossiers", params={"q": part}), 200).json()
    assert [d["domain"] for d in listed["dossiers"]] == [plain[0]]


def test_empty_q_lists_every_dossier(world, plain):
    for domain in plain[:2]:
        assert_status(request(world.alice, domain), 202)
    listed = assert_status(world.alice.get("/dossiers", params={"q": ""}), 200).json()
    assert [d["domain"] for d in listed["dossiers"]] == sorted(plain[:2])


def test_q_without_a_match(world, plain):
    assert_status(request(world.alice, plain[0]), 202)
    listed = assert_status(world.alice.get("/dossiers", params={"q": "zz-no-such-zz"}),
                           200).json()
    assert listed == {"dossiers": [], "has_more": False}


def test_limit_and_offset_page_the_list(world, plain):
    for domain in plain[:3]:
        assert_status(request(world.alice, domain), 202)
    first = assert_status(world.alice.get("/dossiers", params={"limit": 2}), 200).json()
    assert [d["domain"] for d in first["dossiers"]] == sorted(plain[:3])[:2]
    assert first["has_more"] is True
    rest = assert_status(world.alice.get("/dossiers", params={"limit": 2, "offset": 2}),
                         200).json()
    assert [d["domain"] for d in rest["dossiers"]] == sorted(plain[:3])[2:]
    assert rest["has_more"] is False


@pytest.mark.parametrize("limit", ["1", "200"])
def test_limit_bounds_are_accepted(world, plain, limit):
    assert_status(request(world.alice, plain[0]), 202)
    listed = assert_status(world.alice.get("/dossiers", params={"limit": limit}), 200).json()
    assert len(listed["dossiers"]) == 1


@pytest.mark.parametrize("params", [
    {"limit": "0"}, {"limit": "201"}, {"limit": "-1"}, {"limit": "ten"}, {"limit": "1e1"},
    {"limit": "4.0"}, {"limit": "+4"}, {"offset": "-1"}, {"offset": "1.0"}, {"offset": "x"},
], ids=lambda p: "&".join(f"{k}={v}" for k, v in p.items()))
def test_invalid_paging_is_422(world, params):
    assert_error(world.alice.get("/dossiers", params=params), 422, "validation_failed")


def test_unknown_query_parameters_are_ignored(world, plain):
    assert_status(request(world.alice, plain[0]), 202)
    listed = assert_status(world.alice.get("/dossiers", params={"sort": "desc"}), 200).json()
    assert [d["domain"] for d in listed["dossiers"]] == [plain[0]]
