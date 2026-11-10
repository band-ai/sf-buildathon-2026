# Dossier — Stage 1: company profiles

This stage defines the initial service and its API.

Build from the supplied requirements. Source code, API documentation and schemas from
existing products in this domain must not be used.
WebRouter's own documentation may be used.

## 1. Scope

A caller asks for a company by its web domain. The service researches the company on the web
and keeps a **dossier**: a profile of six fields, each with the value the web supports and the
excerpts it came from. A dossier is built in the background, read any number of times, and
refreshed on request. Only the HTTP API is required.

The following apply to all operations, including concurrent requests and retries:

1. Every value the service asserts cites at least one excerpt that a provider endpoint served
   to this service, and that excerpt supports the value. No citation is invented, reworded, or
   attached to a value it does not support.
2. No build of a dossier spends more than 80 units (§9).

Contact data, people search, and fields other than the six in §4 are out of scope.

## 2. Delivery and deployment

Deliver an HTTP service, a `Dockerfile` and a `RUN.md` with a command that builds and
starts the service without manual setup. Language, framework and storage are unrestricted.
A `docker-compose.yml` is optional.

The submission is a containerized HTTP service, not a Python package. Python is not
required in the implementation. TypeScript/JavaScript, Go, Rust, Java, Python and any
other language are equally valid. The submitted `Dockerfile` is built and started,
and only its HTTP behavior is exercised; it does not import or execute the
submission's source files on the host that runs it.

The image must run on its own with `-e PORT=<port>` and a port mapping. All runtime
dependencies, initialization and seed data must work within that single container. Compose
configuration is not used to start the service.

### Web access

Two providers are available: `nimble` and `tavily`. Nimble is the default provider: every
service must be able to research companies using Nimble alone. Tavily is optional: a service
may use it beside Nimble, and its absence must not prevent research while Nimble answers.
The live submission and optional live judging provide a working Nimble key only.

The service reaches the providers only through WebRouter, the Python package `webrouter`
(module `web_router`). The service may be written in any language, but every request to a
provider goes through `web_router`: called in-process, or from a Python helper process that
the service runs inside its own container. The stage folder's dependency manifest lists
`webrouter>=0.12.0`. Calling a provider's API by any other route is not permitted.
Install it and the provider SDK dependencies from PyPI, including in the service's Docker build:

```sh
pip install "webrouter[search,extract,research]>=0.12.0"
```


The deployment provides these environment variables:

| Variable | Meaning |
|---|---|
| `PORT` | The port to listen on (§3.1) |
| `NIMBLE_API_KEY` | Credential for the `nimble` provider |
| `NIMBLE_BASE_URL` | Base URL of the `nimble` provider endpoint |
| `TAVILY_API_KEY` | Credential for the `tavily` provider |
| `TAVILY_BASE_URL` | Base URL of the `tavily` provider endpoint |

Keys are opaque non-empty strings. WebRouter's `nimble` provider reads `NIMBLE_API_KEY` and
`NIMBLE_BASE_URL` from the environment, and its `tavily` provider reads `TAVILY_API_KEY`. A
service that uses Tavily passes its base URL to WebRouter in `provider_config`:

```python
provider_config={"tavily": {"api_base_url": <TAVILY_BASE_URL>}}
```

### Resource limits

The service must operate within these limits:

| Limit | Value |
|---|---|
| CPU | 2 vCPU |
| Memory | 3 GiB |
| Start to first healthy response | 60 s |
| Concurrent requests | up to 50 in flight |
| Per-request timeout | 5 s (10 s for `POST /_test/reset`) |
| Outbound network | available during `docker build`; at run time, **only the provider endpoints this specification lists** |
| Disk | ephemeral; state need not survive a container restart |

Runtime assets and dependencies must be included in the image. This includes fonts,
scripts and stylesheets; external services other than the provider endpoints this
specification lists are unavailable at runtime.

## 3. Runtime contract

### 3.1 Listening

Listen on `0.0.0.0` using the `PORT` environment variable, default `8080`.

### 3.2 Health

```http
GET /health  ->  200  {"status": "ok"}
```

Return 200 once the service and its data store can serve requests, within 60 seconds
of container start. Non-200 responses are permitted before the service is ready.
`/health` makes no provider call.

### 3.3 Reset and seed

```http
POST /_test/reset
Content-Type: application/json

{ ...fixture... }

->  204 No Content
```

Replace all service state with the fixture in the request body (§4). When reset returns
204, subsequent requests must see only that fixture: no users other than the seeded ones,
no dossiers and no stored idempotent responses. Repeated resets are supported. A build
still running when reset is called must not change the state that follows the reset.
This control endpoint must be enabled in the delivered image and requires no authentication.

### 3.4 Clock

The service keeps a clock that only reset and `POST /_test/clock` move. Every timestamp
the service records or returns is read from this clock.

```http
POST /_test/clock
Content-Type: application/json

{ "now": "2026-03-01T09:30:00+00:00" }

->  204 No Content
```

- Reset sets the clock to the fixture's `now`. Before the first reset the clock follows the
  system time.
- The clock stands still between calls: two requests with no clock call between them read
  the same time.
- `now` is an RFC 3339 timestamp with an explicit offset. A `now` earlier than the clock's
  current time is 422 `validation_failed` and changes nothing.
- `POST /_test/clock` requires no authentication.

### 3.5 Conventions

- Requests and responses are `application/json; charset=utf-8`.
- Timestamps in responses are RFC 3339 with an explicit offset, e.g. `2026-09-24T19:00:00+02:00`.
- Unknown fields in a request body are ignored, never an error.
- Unknown query parameters are ignored.
- IDs are opaque strings of at most 64 characters. Their format is yours.

## 4. Model

### Users

Users sign up and log in (§6). Every authenticated user sees the same dossiers.

### Domains

A company is identified by its domain. Every domain the API takes, in a body or a path, is
first **normalised**: surrounding whitespace removed, lowercased, one trailing `.` removed,
and one leading `www.` removed. The normalised domain must then be a valid host name: two or
more labels separated by `.`, each label 1 to 63 characters of `a-z`, `0-9` and `-`, not
starting or ending with `-`, and 253 characters or fewer in total. Anything else, including a
URL with a scheme or a path, is 422 `validation_failed`.

`Acme-Robotics.TEST.`, `www.acme-robotics.test` and `acme-robotics.test` name the same
company and the same dossier. Responses always carry the normalised domain.

### Fields

A dossier has exactly these six fields:

| Field | Value |
|---|---|
| `legal_name` | String: the company's registered name, e.g. `Acme Robotics, Inc.` |
| `hq_city` | String: the city of the company's headquarters, without region or country, e.g. `Lisbon` |
| `ceo` | String: the full name of the company's chief executive, e.g. `Dana Ruiz` |
| `founded_year` | Integer: the year the company was founded, e.g. `2014` |
| `headcount_range` | String: one of `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001-10000`, `10001+` |
| `funding_total` | Integer: total equity funding raised, in whole US dollars, e.g. `12000000` |

A string value is written as the supporting excerpt writes it, without surrounding
whitespace. A headcount the web states as a number, or as a range that fits inside one of
the ranges above, has the range that contains it as its value.

Each field in a response has this shape:

```json
{ "value": "Dana Ruiz", "status": "known",
  "citations": [ { "url": "https://acme-robotics.test/about",
                   "excerpt": "Dana Ruiz has led Acme Robotics as chief executive since 2021.",
                   "provider": "nimble" } ] }
```

- `status` is `known` when `value` is not null, and `unknown` when it is.
- A `known` field has one or more citations. An `unknown` field has `"value": null` and
  `"citations": []`.
- `url` is the URL of the page the excerpt was served for, `provider` is `nimble` or
  `tavily`, the provider that served it.

### Evidence and support

The **evidence** for a company is every page that some search, through any provider and for
any query naming the company (as in Appendix A.2), returns, with its full text, and every
claim that a `nimble` research run for the company asking for all six fields answers with.

Of the searches that a provider answers without an error, every build makes exactly one whose
query is exactly the company's normalised domain, through a provider of its choice; its other
such searches use other queries. A search that a provider answers with an error does not
count. The pages whose text a build obtains from providers are the pages it **gathers**.

A **citation** is an excerpt of text a provider served for the page at `url`:

- The excerpt is copied character for character from that served text, except that any run
  of whitespace may be written as a single space. It is 1 to 500 characters long.
- It is taken from the page's prose (below), not from its header.

An excerpt **supports** a value when, read on its own, it states that value for that field
of this company, as Appendix A defines. The excerpt may write the value differently from the
API: `Acme Robotics has raised $12M.` and `Acme Robotics has raised 12 million dollars.` both
support a `funding_total` of `12000000`, and `Acme Robotics employs about 120 people.`
supports a `headcount_range` of `51-200`.

A research answer carries a claimed value for a field and a citation for the claim. The
claim is asserted only when its citation supports it. A field is `unknown` when no evidence
supports a value for it, even when a research answer claims one.

When the evidence supports more than one value for a field, the field holds one of them and
cites only excerpts that support that value.

### Pages

Every page has a URL, a title and a text. A text may begin with **header lines**, each of
the form `Name: value`, where the name is a capitalised word or several joined by `-`. The
header ends at the first empty line; everything after it is the page's **prose**. A text
whose first line is not a header line has no header and is all prose.

The header line `Facts:` carries a JSON object on the same line. Its keys are field names
from the table above, and its values are what the page states for those fields, in any
format. It is informative only: citations come from the prose, and whether an excerpt
supports a value is decided by Appendix A alone. The service may ignore other header lines.

### Fixture format

```json
{
  "now": "2026-03-01T09:00:00+00:00",
  "users": [
    { "id": "u_ada", "email": "ada@example.com", "password": "correct horse",
      "display_name": "Ada" },
    { "id": "u_bob", "email": "bob@example.com", "password": "correct horse",
      "display_name": "Bob" }
  ]
}
```

- `now` is required and sets the clock (§3.4).
- Seeded users must be able to log in with the given password immediately.
- A fixture with two users sharing an email is a reset error: 422 `validation_failed`,
  changing nothing.

## 5. Errors

Every 4xx and 5xx response carries this body:

```json
{ "error": { "code": "not_found", "message": "human readable, any wording" } }
```

Use the specified HTTP status and `code`. The human-readable `message` may use any wording.
Endpoint-specific errors are listed with each endpoint.

| Status | `code` | When |
|---|---|---|
| 400 | `malformed_request` | Unparseable body, or a field of the wrong JSON type |
| 400 | `missing_idempotency_key` | Required `Idempotency-Key` header absent or empty |
| 401 | `unauthenticated` | Missing, malformed or unknown bearer token |
| 404 | `not_found` | No such resource, or not visible to this caller |
| 409 | `idempotency_key_reuse` | Key already used by this caller with a different request body |
| 422 | `validation_failed` | A required field or query parameter is missing, or a stated rule is violated with no more specific code |

A field of the correct JSON type with an invalid format or out-of-range value gives
422 `validation_failed`, unless an endpoint specifies a different error. In addition:

- An integer-valued **query parameter** is written as plain decimal digits: `1e9`, `4.0` and `+4`
  are 422 `validation_failed` whatever their numeric value.
- Reserve 400 `malformed_request` for a body that does not parse or a field of the wrong type.

Shared ranges, enforced on every endpoint that takes them:

| Field | Valid | Otherwise |
|---|---|---|
| `Idempotency-Key` | 1 to 255 characters | 422 `validation_failed` |
| `limit` | integer 1 to 200 | 422 `validation_failed` |
| `offset` | integer 0 or more | 422 `validation_failed` |

Requests must not produce 5xx responses, including under concurrent load and when a
provider endpoint answers with an error.

## 6. Authentication

Authentication supports signup and login. Email verification, password reset, refresh
tokens and role-management endpoints are out of scope.

```http
POST /auth/signup
{ "email": "a@example.com", "password": "correct horse", "display_name": "Ada" }

->  201  { "user_id": "u_1", "display_name": "Ada", "token": "..." }
```

```http
POST /auth/login
{ "email": "a@example.com", "password": "correct horse" }

->  200  { "user_id": "u_1", "display_name": "Ada", "token": "..." }
```

| Case | Response |
|---|---|
| Email already registered | 409 `email_taken` |
| Password shorter than 8 characters | 422 `validation_failed` |
| `email` not of the form `local@domain` | 422 `validation_failed` |
| `display_name` empty or longer than 100 characters | 422 `validation_failed` |
| Wrong password or unknown email on login | 401 `unauthenticated` |

For a user seeded by the fixture (§3.3), `user_id` is that user's `id` in the fixture.

Every other endpoint requires a bearer token, except `/health`, the `/_test/*` endpoints and
the two above. A request to such an endpoint that lacks a valid token is 401
`unauthenticated`, even when it also lacks a required `Idempotency-Key`.

```http
Authorization: Bearer <token>
```

Tokens do not expire. An account may have multiple valid tokens and concurrent sessions.

Passwords must be stored using a password-hashing function such as bcrypt, scrypt or
Argon2, or an equivalent. Plaintext password storage is not permitted.

## 7. Idempotency

Two write paths require an idempotency key (§8): **`POST /dossiers`** and
**`POST /dossiers/{domain}/refresh`**. Everything below applies to each of them
independently.

```http
Idempotency-Key: <client-chosen string, 1..255 characters>
```

The key is scoped to **the authenticated user**. Two different users may use the same key string
with no interaction between them.

A replay means the same user sending the **same method, the same path and the same body**. The
same key with the same body on a different path is a different request, not a replay, and must
succeed normally. `Acme-Robotics.test` and `acme-robotics.test` in a path or body are different
requests for this rule, though they name the same dossier.

| Situation | Response |
|---|---|
| Header absent or empty | 400 `missing_idempotency_key` |
| First use of the key | The normal response (§8) |
| Replay: same key, same body | **200**, body identical to the original response as a JSON value |
| Same key, different body | 409 `idempotency_key_reuse` |
| Key reused after the original request failed with 4xx | Treated as a first use |

"Same body" means the same JSON value after parsing — key order and whitespace do not matter.
Unknown fields are ignored (§3.5) and play no part in this comparison: a body that differs
from the first only in unknown fields is the same body, so the request is a replay.
`POST /dossiers/{domain}/refresh` takes no body; any body sent to it is ignored and plays no
part in deciding a replay.

For concurrent identical requests with an unused key, exactly one returns the normal
response. The others return 200 with the same body. The operation takes effect only once.

A successful replay returns the original response, even after the dossier has changed. It
starts no build and makes no provider call.

After the body has parsed as a JSON object and the caller is authenticated, an already
claimed key is resolved before field validation. Thus changing a successful request to an
invalid body with the same key still returns `409 idempotency_key_reuse`.

## 8. API

### Builds

A **build** researches one dossier: it calls the providers, decides each field, and replaces
the dossier's fields with the result when it completes. A dossier's first build starts with
`POST /dossiers`, and every later one with `POST /dossiers/{domain}/refresh`. A build's
**time** is the clock's time when the request that started it was received.

- A dossier has at most one build running at a time.
- A build ends in `ready` when it completed, or `failed` when none of its provider calls
  succeeded. A failed build leaves the fields as they were.
- When a build completes `ready`, each field is `known` exactly when the evidence (§4)
  supports a value for it.
- A build whose provider calls each answer within one second ends within 10 seconds of the
  request that started it.
- Reading a dossier, listing dossiers and every other request except `POST /dossiers` and
  `POST /dossiers/{domain}/refresh` make no provider call.

### `POST /dossiers`

**An idempotent write path.** `Idempotency-Key` is required; see §7.

```http
POST /dossiers
Authorization: Bearer <token>
Idempotency-Key: 2f9c1a...

{ "domain": "acme-robotics.test" }
```

```json
202
{ "dossier_id": "d_7", "domain": "acme-robotics.test", "state": "building" }
```

When no dossier exists for the domain, the service creates one, starts its first build and
returns 202. When a dossier already exists for the domain, the service starts no build and
returns **200** with that dossier's `dossier_id`, `domain` and current `state`.

Concurrent requests for the same domain create one dossier and start one build, whatever
their keys.

| Case | Response |
|---|---|
| `domain` missing | 422 `validation_failed` |
| `domain` invalid after normalisation (§4) | 422 `validation_failed` |

### `GET /dossiers/{domain}`

```json
{
  "dossier_id": "d_7",
  "domain": "acme-robotics.test",
  "state": "ready",
  "researched_at": "2026-03-01T09:00:00+00:00",
  "spent_units": 34,
  "fields": {
    "legal_name": { "value": "Acme Robotics, Inc.", "status": "known", "citations": [ { "...": "..." } ] },
    "hq_city": { "value": "Lisbon", "status": "known", "citations": [ { "...": "..." } ] },
    "ceo": { "value": null, "status": "unknown", "citations": [] },
    "founded_year": { "value": 2014, "status": "known", "citations": [ { "...": "..." } ] },
    "headcount_range": { "value": "51-200", "status": "known", "citations": [ { "...": "..." } ] },
    "funding_total": { "value": 12000000, "status": "known", "citations": [ { "...": "..." } ] }
  }
}
```

- `state` is `building` while a build runs, otherwise the outcome of the latest build,
  `ready` or `failed`.
- `fields` always holds all six fields. Before the first build completes `ready`, every
  field is `unknown`. While a later build runs, `fields` are those of the last build that
  completed `ready`.
- `researched_at` is the time of the last build that completed `ready`, or null.
- `spent_units` is the total cost (§9) of every provider call made for this dossier, by
  every build, since it was created.
- The domain in the path is normalised (§4). No dossier for it is 404 `not_found`.

### `POST /dossiers/{domain}/refresh`

**An idempotent write path.** `Idempotency-Key` is required; see §7. No body.

Starts a new build of the dossier and returns 202 with
`{ "dossier_id", "domain", "state": "building" }`. A refresh received while a build of the
dossier is running starts no second build and returns 202 with the same body.

A refresh researches again: its build makes provider calls whether or not anything has
changed since the last build, and its spending counts in `spent_units`.

| Case | Response |
|---|---|
| No dossier for the domain | 404 `not_found` |

### `GET /dossiers`

```http
GET /dossiers?q=acme&limit=50&offset=0
```

```json
{ "dossiers": [ { "dossier_id": "d_7", "domain": "acme-robotics.test", "state": "ready",
                  "legal_name": "Acme Robotics, Inc.", "researched_at": "2026-03-01T09:00:00+00:00",
                  "spent_units": 34 } ],
  "has_more": false }
```

- `legal_name` is the value of the dossier's `legal_name` field, or null.
- `q` is optional. When present, only dossiers whose domain or `legal_name` contains `q`,
  compared case-insensitively, are listed. An empty `q` lists every dossier.
- Dossiers are ordered by domain ascending.
- `limit` defaults to 50, range 1 to 200. `offset` defaults to 0. `has_more` is true when
  items exist beyond the last one returned.

## 9. Providers and cost

Each provider call has a cost in **units**:

| Call | Cost |
|---|---|
| Search through `nimble`, depth `lite` (title, URL and snippet) | 1 |
| Search through `nimble`, depth `fast` (a truncated page body) | 5 |
| Search through `nimble`, depth `deep` (the full page) | 15 |
| Search through `tavily`, depth `lite` (title, URL and snippet) | 8 |
| Search through `tavily`, depth `fast` (title, URL and a longer snippet) | 16 |
| Search through `tavily`, depth `deep` (the full page) | 16 |
| Extract through `nimble` | 1 per URL requested, including a URL for which no page is returned |
| Extract through `tavily` | 2 per URL requested, including a URL for which no page is returned |
| Research run through `nimble` | 25 when the run is started; checking on or collecting a run costs nothing |

A search's depth is WebRouter's `search_depth`.

A search returns at most 10 results, whatever number it asks for. A call that a provider
refuses with an error status costs nothing. A call whose answer does not arrive, because it
times out or its connection fails, costs its units as in the table, whether or not the
provider received it. An extract that the provider answers with no page
for the URL is not refused: it costs its units, as in the table, whatever status says so. An
extract through `nimble` does not set `render`.

A build stops making provider calls before its spending would exceed 80 units, and completes
with the pages and research claims it has obtained.

A research request names the company by its domain in its query, and names the fields it
asks for by the field names in §4, as the property names of its output schema.

## 10. Export and import

The service must support `GET /_test/export` and `POST /_test/import`. Like reset, these
are unauthenticated control endpoints.
Exports may contain credentials and session tokens; handle them as private artifacts.
Return 200 from export with a JSON object containing `track: "dossier"`,
`format_version: 1` and `state` (an implementation-defined JSON object). The state format
is opaque to the caller and must be accepted unchanged by import.

Import takes that entire object and atomically replaces the service's state, returning
204. It must accept an unchanged export produced by this service. No dependency on the
source process, files, volume, port or network address is allowed. Import is replacement,
not merge; repeating it restores the exported state without duplicating anything. Invalid
JSON follows §5; missing fields, wrong track/version or an invalid state give 422
`validation_failed` without changing the destination. These control calls have a 10-second
timeout. Export is an atomic, read-only snapshot; subsequent source writes do not change it.

Preserve accounts and hashed-password login, existing bearer tokens, dossiers with their
ids, states, fields, citations, `researched_at` and `spent_units`, all completed idempotent
request bodies and original responses. Identities and timestamps must not be regenerated.
Import makes no provider call: imported dossiers are not researched again, and their
citations remain citations served to this service. Failed request keys remain reusable.
Existing tokens and retries must remain valid after import; replacing the state with a fresh
fixture does not satisfy this requirement. Import removes all previous destination data and
credentials. Reset clears all state, including imported state. Export and import do not
change the clock. State need not survive an abrupt container restart.

An export taken while a build is running holds the dossier as it was before that build;
after import, that dossier is in the state of its last completed build, or `failed` with
every field `unknown` when no build had completed.

## 11. Concurrency

Concurrent requests must produce the same results as executing them one at a time in some
order. The requirements above hold at every read.

## Appendix A. When an excerpt supports a value

This appendix is the whole definition of "supports" used in §4. The service decides support
by these rules alone.

### A.1 Sentences

A page's prose is split into lines at each line break, and each line into sentences. A
sentence ends after a `.`, `!` or `?`, together with any `"`, `”`, `’` or `)` directly after
it, when whitespace follows. A `.` that ends one of the legal-form suffixes in A.4, written
as a whole word, does not end a sentence. Each sentence is taken without its surrounding
whitespace; empty sentences are dropped.

An excerpt is a **single sentence** when, with every run of whitespace written as one space,
this rule splits it into exactly one sentence.

### A.2 The rule

An excerpt supports the value V for the field F of a company exactly when all of these hold:

1. It is a single sentence (A.1).
2. It names the company: it contains the company's normalised domain, or the company's
   name. The company's name is the first label of its domain with each `-` read as a space:
   `acme-robotics.test` is named by `Acme Robotics`.
3. It contains a statement phrase for F (A.3).
4. It contains none of the negating phrases (A.3).
5. It contains at least one value in F's format (A.4), and every value in F's format that it
   contains normalises to V (A.5).

The company's name, its domain and every phrase are matched without regard to case and as
whole words: the characters directly before and after the match are not letters or digits.
Phrases with a space match one space.

For example, for `acme-robotics.test`:

| Excerpt | Supports |
|---|---|
| `Dana Ruiz has led Acme Robotics as chief executive since 2021.` | `ceo` `Dana Ruiz` |
| `Acme Robotics CEO: Sam Ortiz.` | `ceo` `Sam Ortiz` |
| `Acme Robotics was founded in 2014.` | `founded_year` `2014` |
| `Acme Robotics employs about 120 people.` | `headcount_range` `51-200` |
| `Acme Robotics is reportedly in talks to raise $40M.` | nothing: a negating phrase |
| `Acme Robotics opened a sales office in Porto.` | nothing: no statement phrase for `hq_city` |

### A.3 Phrases

| Field | Statement phrases |
|---|---|
| `legal_name` | `legal name`, `registered name`, `registered as`, `registered company`, `legal entity`, `name of record` |
| `hq_city` | `headquartered in`, `headquarters in`, `head office in`, `based in`, `registered office in`, `registered seat in` |
| `ceo` | `chief executive officer`, `chief executive`, `CEO` |
| `founded_year` | `founded`, `founding`, `established`, `incorporated` |
| `headcount_range` | `employs`, `employees`, `staff`, `people`, `headcount`, `workforce` |
| `funding_total` | `raised`, `funding`, `invested`, `investment` |

The negating phrases are: `in talks to`, `plans to`, `planning to`, `wants to`,
`expects to`, `hopes to`, `aims to`, `seeking`, `could`, `would`, `might`, `reportedly`,
`rumoured`, `former`, `formerly`, `will become`, `not`.

### A.4 Value formats

A **capitalised word** is an uppercase letter `A`–`Z` followed by one or more lowercase
letters `a`–`z`, with no letter or digit directly before or after it.

A **number** is written in digits, optionally with a `,` before each group of three digits
and a decimal part after a `.`: `120`, `1,200`, `12.5`, `12,000,000`. Digits directly next to
a letter, or joined to other digits by `,` or `.` in any other way, are not a number.

| Field | Format |
|---|---|
| `legal_name` | The company's name or its domain (matched as in A.2), then zero or more capitalised words each after one space, then an optional `,`, one space, and a legal-form suffix with no letter or digit directly after it. Where several such texts start at the same place, the shortest counts |
| `hq_city` | A place name directly after a statement phrase for `hq_city` and one space: the longest run of capitalised words joined by single spaces or by `-` that starts there, not part of a longer such run |
| `ceo` | A person's name: a run of two or three capitalised words joined by single spaces that is not part of a longer such run. Occurrences of the company's name and of the statement phrases for `ceo` are first taken out of the sentence and separate the words around them |
| `founded_year` | A number of exactly four digits, from 1800 to 2099, that is not part of an amount |
| `headcount_range` | A number with no decimal part, 1 or more, that is not part of an amount. Words before it, such as `about` or `roughly`, do not change it. A stated range such as `51-200 employees` holds two numbers |
| `funding_total` | An amount (below) |

The legal-form suffixes, matched exactly as written here: `Inc.`, `Corp.`, `LLC`, `LLP`,
`L.P.`, `Ltd`, `Limited`, `Pty Ltd`, `plc`, `PLC`, `GmbH`, `AG`, `KG`, `SE`, `AS`, `A/S`,
`ASA`, `AB`, `Oy`, `Oyj`, `B.V.`, `N.V.`, `S.A.`, `S.A.S.`, `S.L.`, `S.r.l.`, `S.p.A.`,
`s.r.o.`, `a.s.`, `K.K.`.

An **amount** is written in one of these forms, matched without regard to case, with no
letter or digit directly before it or after it:

- `$`, `US$` or `USD`, an optional space, a number, and optionally a scale: `k`, `m`, `mn` or
  `bn` directly after the number, or one space and `thousand`, `million` or `billion`.
  Examples: `$12M`, `$12.5 million`, `US$12 million`, `USD 12 million`, `$12m`,
  `$12,000,000`.
- A number, optionally one space and `thousand`, `million` or `billion`, then one space and
  `dollars` or `US dollars`. Examples: `12 million dollars`, `12,000,000 US dollars`.

Amounts in other currencies are not amounts.

### A.5 Normalisation

| Field | Normalised value |
|---|---|
| `legal_name`, `hq_city`, `ceo` | The text as the excerpt writes it |
| `founded_year` | The number as an integer |
| `headcount_range` | The range of §4 that contains the number |
| `funding_total` | The number times the scale (`k` and `thousand` 1,000; `m`, `mn` and `million` 1,000,000; `bn` and `billion` 1,000,000,000) in US dollars. An amount that does not come to a whole number of dollars is not a value |
