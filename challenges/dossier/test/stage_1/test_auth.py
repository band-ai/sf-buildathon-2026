"""Signup, login and bearer tokens (§6), and the control endpoints that set up every check:
reset (§3.3) and the clock (§3.4).

Validation failures carry the §5 envelope with the specified status and code; tokens do not
expire and several may be live for one account; reset replaces every user, dossier and
stored idempotent response; the clock moves only by reset and `POST /_test/clock`.
"""
# pylint: disable=missing-function-docstring,unused-argument,too-many-arguments
# pylint: disable=too-many-positional-arguments
import pytest

import fixtures as fx
from harness.http import assert_error, assert_status, new_key

pytestmark = pytest.mark.stage(1)

DEE = {"email": "dee@example.com", "password": "correct horse", "display_name": "Dee"}


def signup(api, **over):
    """POST /auth/signup with Dee's details, overridden by `over`."""
    return api().post("/auth/signup", json={**DEE, **over}, token=None)


def relogin(api):
    """Alice signed in again; a reset leaves no session to rely on."""
    return api().authenticate(fx.ALICE["email"], fx.ALICE["password"])


# ---- signup and login ------------------------------------------------------

def test_signup_token_works_at_once(world, api):
    body = assert_status(signup(api), 201).json()
    assert body["display_name"] == "Dee" and body["user_id"] and body["token"]
    assert_status(api(body["token"]).get("/dossiers"), 200)


def test_login_returns_the_signed_up_user(world, api):
    signed = assert_status(signup(api), 201).json()
    logged = assert_status(api().login(DEE["email"], DEE["password"]), 200).json()
    assert logged["user_id"] == signed["user_id"] and logged["display_name"] == "Dee"
    assert_status(api(logged["token"]).get("/dossiers"), 200)


def test_seeded_users_log_in(world, api):
    for user in (fx.ALICE, fx.BOB):
        body = assert_status(api().login(user["email"], user["password"]), 200).json()
        assert body["display_name"] == user["display_name"] and body["token"]


@pytest.mark.parametrize("email", [DEE["email"], fx.ALICE["email"]])
def test_email_already_registered(world, api, email):
    if email == DEE["email"]:
        assert_status(signup(api), 201)
    assert_error(signup(api, email=email), 409, "email_taken")


@pytest.mark.parametrize("password", ["", "short12"])
def test_password_shorter_than_eight(world, api, password):
    assert_error(signup(api, password=password), 422, "validation_failed")


def test_eight_character_password_is_enough(world, api):
    assert_status(signup(api, password="12345678"), 201)


@pytest.mark.parametrize("email", ["plain", "@example.com", "dee@", ""])
def test_email_not_local_at_domain(world, api, email):
    assert_error(signup(api, email=email), 422, "validation_failed")


@pytest.mark.parametrize("display_name", ["", "x" * 101])
def test_display_name_empty_or_too_long(world, api, display_name):
    assert_error(signup(api, display_name=display_name), 422, "validation_failed")


def test_display_name_of_100_characters(world, api):
    assert_status(signup(api, display_name="x" * 100), 201)


@pytest.mark.parametrize("field,value", [("email", 7), ("password", ["correct horse"]),
                                         ("display_name", False)])
def test_signup_field_of_the_wrong_type(world, api, field, value):
    assert_error(signup(api, **{field: value}), 400, "malformed_request")


@pytest.mark.parametrize("field", ["email", "password", "display_name"])
def test_signup_field_missing(world, api, field):
    body = {k: v for k, v in DEE.items() if k != field}
    assert_error(api().post("/auth/signup", json=body, token=None), 422, "validation_failed")


@pytest.mark.parametrize("path", ["/auth/signup", "/auth/login"])
def test_unparseable_body(world, api, path):
    assert_error(api().post(path, content="{not json", token=None), 400, "malformed_request")


def test_login_field_of_the_wrong_type(world, api):
    resp = api().post("/auth/login", json={"email": fx.ALICE["email"], "password": 123},
                      token=None)
    assert_error(resp, 400, "malformed_request")


def test_login_field_missing(world, api):
    resp = api().post("/auth/login", json={"email": fx.ALICE["email"]}, token=None)
    assert_error(resp, 422, "validation_failed")


@pytest.mark.parametrize("email,password", [(fx.ALICE["email"], "wrong horse"),
                                            ("nobody@example.com", "correct horse")])
def test_wrong_password_or_unknown_email(world, api, email, password):
    assert_error(api().login(email, password), 401, "unauthenticated")


def test_unknown_body_fields_are_ignored(world, api):
    assert_status(signup(api, nickname="dee", referrer=None), 201)


def test_several_tokens_stay_valid(world, api):
    first = assert_status(api().login(fx.ALICE["email"], fx.ALICE["password"]), 200)
    second = assert_status(api().login(fx.ALICE["email"], fx.ALICE["password"]), 200)
    for token in (first.json()["token"], second.json()["token"], world.alice.token):
        assert_status(api(token).get("/dossiers"), 200)


# ---- bearer tokens --------------------------------------------------------

ENDPOINTS = [("GET", "/dossiers", None), ("GET", "/dossiers/{d}", None),
             ("POST", "/dossiers", {"domain": "{d}"}), ("POST", "/dossiers/{d}/refresh", None)]


def call(client, endpoint, domain, **kw):
    """Send one of ENDPOINTS for `domain` with an idempotency key."""
    method, path, body = endpoint
    json = {k: v.format(d=domain) for k, v in body.items()} if body else None
    return client.request(method, path.format(d=domain), json=json,
                          idempotency_key=new_key(), **kw)


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda e: f"{e[0]} {e[1]}")
@pytest.mark.parametrize("auth", [None, "Bearer not-a-token"], ids=["missing", "unknown"])
def test_endpoint_needs_a_valid_token(world, api, plain, endpoint, auth):
    headers = {"Authorization": auth} if auth else None
    resp = call(api(), endpoint, plain[0], token=None, headers=headers)
    assert_error(resp, 401, "unauthenticated")


@pytest.mark.parametrize("auth", ["Bearer", "Basic YWxpY2U6Y29ycmVjdA==", "{token}"])
def test_malformed_authorization_header(world, api, auth):
    headers = {"Authorization": auth.format(token=world.alice.token)}
    resp = api().get("/dossiers", token=None, headers=headers)
    assert_error(resp, 401, "unauthenticated")


def test_health_needs_no_token_and_calls_no_provider(world, anon, web):
    assert assert_status(anon.get("/health"), 200).json() == {"status": "ok"}
    assert web.log() == []


# ---- reset ---------------------------------------------------------------

def test_reset_with_a_shared_email_changes_nothing(world, api, reset):
    assert_status(signup(api), 201)
    clash = dict(fx.BOB, email=fx.ALICE["email"])
    assert_error(reset({"now": fx.NOW, "users": [fx.ALICE, clash]}, raw=True),
                 422, "validation_failed")
    assert_status(api().login(DEE["email"], DEE["password"]), 200)
    assert_status(world.alice.get("/dossiers"), 200)


def test_reset_needs_now(world, reset):
    assert_error(reset({"users": [fx.ALICE, fx.BOB]}, raw=True), 422, "validation_failed")


def test_reset_removes_signed_up_users(world, api, reset):
    assert_status(signup(api), 201)
    reset(world.fixture)
    assert_error(api().login(DEE["email"], DEE["password"]), 401, "unauthenticated")
    relogin(api)


def test_reset_removes_dossiers(world, api, reset, build, plain):
    build(plain[0])
    reset(world.fixture)
    alice = relogin(api)
    assert_error(alice.get(f"/dossiers/{plain[0]}"), 404, "not_found")
    assert assert_status(alice.get("/dossiers"), 200).json()["dossiers"] == []


def test_reset_forgets_idempotent_responses(world, api, reset, settle, plain):
    key = new_key()
    assert_status(world.alice.post("/dossiers", json={"domain": plain[0]},
                                   idempotency_key=key), 202)
    settle(plain[0])
    reset(world.fixture)
    alice = relogin(api)
    assert_status(alice.post("/dossiers", json={"domain": plain[0]}, idempotency_key=key), 202)


def test_repeated_resets(world, api, reset):
    for _ in range(3):
        reset(world.fixture)
    relogin(api)


# ---- clock ---------------------------------------------------------------

def test_clock_dates_the_build(world, clock, build, plain):
    later = "2026-03-02T10:30:00+02:00"
    assert_status(clock(later), 204)
    assert fx.instant(build(plain[0])["researched_at"]) == fx.instant(later)


def test_clock_cannot_move_back(world, clock, build, plain):
    assert_error(clock("2026-03-01T08:59:59+00:00"), 422, "validation_failed")
    assert fx.instant(build(plain[0])["researched_at"]) == fx.instant(fx.NOW)


def test_clock_needs_an_offset(world, clock, build, plain):
    assert_error(clock("2026-03-02T09:00:00"), 422, "validation_failed")
    assert fx.instant(build(plain[0])["researched_at"]) == fx.instant(fx.NOW)


def test_reset_sets_the_clock(world, clock, api, reset, build, plain):
    assert_status(clock("2026-04-01T00:00:00+00:00"), 204)
    reset(world.fixture)
    world.alice = relogin(api)
    assert fx.instant(build(plain[0])["researched_at"]) == fx.instant(fx.NOW)
