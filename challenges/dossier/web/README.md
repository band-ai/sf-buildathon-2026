# Mock web

A local test double for the four provider endpoints a Dossier service calls. It answers as
Nimble, Tavily, Kernel and Browserbase, with their APIs' request and response shapes as
WebRouter 0.12.0, `nimble-python` and `tavily-python` call them, from a corpus of fictional companies
on reserved `.test` domains. There is no internet access and no model behind it: every answer
comes from the corpus files, and the same request against the same corpus and epoch always
gets the same answer.

Use it to develop and check a service offline. The sample corpus in `corpus/sample/` ships
with it.

## Running it

The image reads its corpus from `/data/corpus` and listens on port 8080. It answers each request
on its own thread, with a listen backlog of 128 connections.

```sh
docker build -t dossier-web challenges/dossier/web
docker network create dossier
docker run --rm -d --name web --network dossier \
  -e MOCK_ADMIN_TOKEN=local-admin \
  -v "$PWD/challenges/dossier/web/corpus/sample:/data/corpus:ro" \
  -p 8080:8080 dossier-web
```

Then start the service on the same network with the provider variables pointing at it:

```sh
docker run --rm --network dossier -p 8000:8000 \
  -e PORT=8000 \
  -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://web:8080/nimble \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://web:8080/tavily \
  -e KERNEL_API_KEY=local -e KERNEL_BASE_URL=http://web:8080/kernel \
  -e BROWSERBASE_API_KEY=local -e BROWSERBASE_BASE_URL=http://web:8080/browserbase \
  my-dossier-service
```

The keys can be any non-empty string; the mock does not check them. `curl
http://localhost:8080/_mock/health` answers `{"status": "ok"}` once the corpus has loaded.
Without `MOCK_ADMIN_TOKEN` the admin API below is disabled and every admin route answers 404.

## Against the live web

To try a real company, start the service without the mock and give it your own Nimble key.
This spends real units and is not how any scored check runs. The participant guide, The
repository you submit, has the commands: they start the service with every variable the specs
list and produce `dossier-runway.com.json`.

Set each `*_BASE_URL` to the provider's real endpoint or leave it out; never pass it empty.
`nimble-python` falls back to `https://sdk.nimbleway.com` only when `NIMBLE_BASE_URL` is unset.
An empty value counts as set, so every call fails with `Connection error` (`Request URL is
missing an 'http://' or 'https://' protocol`) and the build ends `failed`.

## Provider routes

One container serves all four providers under path prefixes:

| Provider | Base URL | Routes |
|---|---|---|
| Nimble | `http://<host>:8080/nimble` | `POST /v2/search`, `POST /v2/extract`, and the agent-run routes under `/v2/agents/` that `nimble-python` 1.6 calls to start a run, read its status and fetch its result |
| Tavily | `http://<host>:8080/tavily` | `POST /search` and `POST /extract`, the paths `tavily-python` calls under its `api_base_url` |
| Kernel | `http://<host>:8080/kernel` | `POST /browsers`, `GET /browsers/{id}`, `DELETE /browsers/{id}` |
| Browserbase | `http://<host>:8080/browserbase` | `POST /v1/sessions`, `GET /v1/sessions/{id}`, `POST /v1/sessions/{id}` (release), `POST /v1/agents/runs`, `GET /v1/agents/runs/{id}`, `POST /v1/agents/runs/{id}/stop` |

Request and response shapes are the ones WebRouter 0.12.0 sends and parses for these
providers, which are also the ones `nimble-python` and `tavily-python` use. A client of a
provider's own API points at the provider's base URL above. Through WebRouter, its `nimble`
provider is redirected by `NIMBLE_BASE_URL`; the others take their base URLs from
`provider_config`:

```python
provider_config={"tavily": {"api_base_url": TAVILY_BASE_URL},
                 "kernel": {"base_url": KERNEL_BASE_URL},
                 "browserbase": {"base_url": BROWSERBASE_BASE_URL}}
```

Every provider serves every page of the current epoch. Tavily has no research route. The
Nimble template routes `nimble-python` calls answer an empty catalogue, and Nimble's not-found
error for any template name.

### Search

Search ranks the pages of the current epoch by keyword relevance (BM25) of the query to each
page's title and served text, ties broken by URL, and returns up to the requested number of
results, and never more than 10. A request without a number gets the provider's default
(Nimble 10, Tavily 5); a negative number is answered 400.
A query containing a company's domain ranks that company's
pages above every other page. A page whose `searchable` is false is never returned by a
search.

Each provider perturbs the relevance scores by its own seeded noise from the set's
`traits.json` (below), so providers order the same pages differently, and a provider orders
them the same way every time.

| What the request asks for | What each result carries |
|---|---|
| Nimble `lite` (WebRouter `search_depth="lite"`) | Title, URL and a snippet: the first 300 characters of the page's prose |
| Nimble `standard` (WebRouter `fast`) | Title, URL and the first 1500 characters of the served text |
| Nimble `standard` with full content (WebRouter `deep`) | Title, URL and the whole served text |
| Tavily `basic` (WebRouter `lite`) | Title, URL and the snippet as for `lite` in `content` |
| Tavily `advanced` (WebRouter `fast`) | Title, URL and the first 450 characters of the page's prose in `content` |
| Tavily `advanced` with `include_raw_content` (WebRouter `deep`) | As for `fast`, plus the whole served text in `raw_content` |

### Extract

Nimble extract and Tavily extract return the whole served text of
a page by URL, whether or not the page is `searchable`. A Nimble extract with `render: true`
(WebRouter `provider_options={"render": True}`, `nimble-python` `render=True`) loads the page
in a browser and returns the text the browser shows once it has loaded, before any disclosure
control is activated: Nimble clicks nothing. A URL with no page in the current
epoch gets that provider's failure answer for the URL: Nimble a failed `status`,
Tavily an entry in `failed_results`.

### Research

A research run completes on the first poll. Its answer is resolved this way:

1. **Company.** The first `.test` domain in the query that belongs to a corpus company names
   it. Without one, the first of a company's `names` found in the query, compared
   case-insensitively. With neither, the run answers with no structured values and no
   citations.
2. **Fields.** The property names of the request's `output_schema` that are Dossier field
   names (`legal_name`, `hq_city`, `ceo`, `founded_year`, `headcount_range`,
   `funding_total`). Other property names get null.
3. **Answer.** For each field, the company's `research` entries for this provider and the
   current epoch give the `structured` value. A field with no entry is null.
4. **Citations.** Nimble research returns one citation per field that has a value, with
   `url`, `snippet` set to the entry's `excerpt`, and `field` set to the field's JSON path
   into the answer (`$.legal_name`), as real Nimble names it. A citation may point at a
   page that is not `searchable`.

### Browser sessions

Opening a Kernel or Browserbase session starts a headless Chromium inside the mock container.
The session's DevTools URL (`cdp_ws_url`, `connectUrl`) is a `ws://` URL on the same host and
port the client used, so a client that reaches the mock reaches its sessions. In a session,
every `.test` host of the current epoch answers over HTTPS with its page, and every other host
fails to resolve. Each provider keeps at most 4 sessions open at once; a fifth open is answered
429 and costs nothing. A session with no DevTools client for 60 seconds is closed.

Neither the sample nor the sealed graded corpus contains disclosure controls or facts that
require clicking. Nimble's rendered extract suffices for all graded browser text, so Kernel
and Browserbase remain optional. The mock also supports disclosure controls for custom,
ungraded experiments: `<button aria-expanded="false" aria-controls="...">`
elements, each written on a line of its own after the text that shows when the page has
loaded. Clicking one sets its `aria-expanded` to `"true"` and shows, on the lines after it,
the text it discloses and any controls nested in it, each again `aria-expanded="false"`.
Clicks request nothing from the mock, so they cost nothing. Search, extract and Nimble's
render serve such a page as it shows before any click: its text, then the label of each
control that is not nested in another.

A Browserbase agent run reads the first `http://` or `https://` URL in its task, and completes
with that page's text, every disclosure control activated, as its summary. A task with no
URL, or with a URL that has no page in the current epoch, finishes failed. A Browserbase
session's `/debug` route answers 404.

### Served text

The served text of a page is its header lines, one empty line, then the page's `text`:

```
Kind: news
Published: 2026-02-20T00:00:00Z
Effective: 2026-02-15
Registrant: dailyledger.test
Canonical: https://wire.test/acme-raises
First-Published-By: wire.test
Facts: {"funding_total": "$12M", "ceo": "Dana Ruiz"}

Acme Robotics raised $12M in a round led by ...
```

| Header line | From the corpus page | Omitted when |
|---|---|---|
| `Kind` | `kind` | null |
| `Published` | `published_at` | null |
| `Effective` | `true_from` | null |
| `Registrant` | `lineage.registrant` | never |
| `Canonical` | `lineage.canonical` | null |
| `First-Published-By` | `lineage.first_published_by` | null |
| `Facts` | `facts`, as compact JSON | empty |

## Cost

Every call has a cost in units, recorded in the call log:

| Call | Nimble | Tavily |
|---|---|---|
| Search, WebRouter `lite` / `fast` / `deep` | 1 / 5 / 15 | 8 / 16 / 16 |
| Extract, per URL requested | 1 | 2 |
| Nimble extract with `render: true`, per URL requested | 3 | — |
| Research, when the run is created | 25 | — |

| Call | Kernel | Browserbase |
|---|---|---|
| Open a session | 0 | 2 |
| Each page served to a session | 1 | 1 |
| Agent run, when it completes | — | 4 |

Status and result polls of a research run cost nothing. Releasing a session, a failed open, an agent run that fails, and a page
request answered 404 cost nothing. An extract of a URL with no page
costs the same as one with a page, however the provider reports it. A fault answer (500 or
429) costs 0. A client that retries a faulted call makes one log entry per attempt, each
costing 0.

One unit is about $0.001. Search, extract and Nimble research follow each provider's
published list price at that rate, rounded to whole units; a Tavily extract (list price 1.6
units a URL) and a browser page (a fraction of a unit) are rounded up, per URL and per page. Browserbase sessions and browse runs, Nimble's `render` surcharge, ranking
noise and rate limits are set for this challenge and say nothing about the real vendors'
prices, ranking quality or reliability.

## Corpus files

One JSON file per company, `corpus/<set>/<domain>.json`:

```json
{"domain": "acme-robotics.test", "names": ["Acme Robotics"],
 "pages": [{"url": "...", "kind": "own|filing|news|aggregator",
            "epochs": [0, 1], "searchable": true, "published_at": "2026-03-01T00:00:00Z", "true_from": "2026-02-15",
            "title": "...", "text": "...",
            "facts": {"<field>": "<value as the page states it>"},
            "lineage": {"canonical": "url|null", "first_published_by": "domain|null", "registrant": "domain"}}],
 "research": {"nimble": {"<epoch>": [{"field": "ceo", "value": "...", "url": "...", "excerpt": "..."}]}}}
```

| Key | Meaning |
|---|---|
| `domain` | The company's domain, ending in `.test` |
| `names` | Names the company goes by, for research resolution |
| `pages[].url` | The page's URL. A URL may appear in several entries whose `epochs` do not overlap |
| `pages[].kind`, `published_at`, `true_from`, `lineage`, `facts` | Rendered as header lines (above) |
| `pages[].epochs` | The epochs in which the page is served |
| `pages[].searchable` | Optional, default true. False: the page is served by extract and cited by research, but no search returns it |
| `pages[].title`, `text` | The page's title and prose |
| `research` | Research entries per provider and epoch; each `excerpt` is text of the page at `url` |

A set carries a `traits.json` beside the company files, giving each provider's ranking noise
and rate limit:

```json
{"seed": 1234, "providers": {"nimble": {"noise": 0.3, "rate_limit": 0.1},
                             "tavily": {"noise": 0.2, "rate_limit": 0}}}
```

A provider's score for a page is `bm25 * (1 + noise * h)`, where `h` in [-1, 1) is derived
from `sha256(f"{seed}:{provider}:{url}")`. A provider missing from `providers` has noise 0
and rate limit 0, and a set without the file ranks every provider by plain BM25. The values
are drawn per corpus set, so the sample set's traits say nothing about the set used for
grading, which has its own draw.

A set may also carry a `key.json` beside the company files. It holds data the shipped checks
read, keyed by domain, and is never served. Its `supports` list, where present, labels each
excerpt of a page's `text` with the field and canonical value it supports by the rule in
`stage-1.md` Appendix A:

```json
{"acme-robotics.test": {"supports": [{"url": "https://acme-robotics.test/about",
                                      "excerpt": "...", "field": "ceo", "value": "Dana Ruiz"}]}}
```

## Admin API

The admin API controls the mock during a test run. Every admin request carries the header
`X-Mock-Admin: <token>`, where the token is the container's `MOCK_ADMIN_TOKEN`. A request
without the right token gets 404, as if the route did not exist.

| Request | Effect |
|---|---|
| `POST /_mock/reset` `{"epoch": 0}` → 204 | Clears the call log and every fault, turns the weather off, ends every browser session, and sets the epoch |
| `POST /_mock/epoch` `{"epoch": n}` → 204 | Sets the epoch: the pages and research entries served from now on are those of epoch `n` |
| `POST /_mock/faults` `{"provider": "nimble", "methods": ["search", "extract", "research"], "mode": "error"}` → 204 | From now on, the provider (`nimble`, `tavily`, `kernel` or `browserbase`) answers the listed methods (`search`, `extract`, `research`, `session`, `browse`) with 500 (`error`) or 429 (`rate_limit`); `none` clears the fault. For research and browse, a fault applies to creating a run; for `session`, to opening a session |
| `POST /_mock/faults` `{"provider": "nimble", "methods": ["research"], "mode": "throttle"}` → 204 | From now on, the provider answers 429 to the first attempt, since the throttle was set, of each distinct call to the listed methods, and answers later attempts normally where the rate limits below allow |
| `POST /_mock/faults` `{"provider": "tavily", "methods": ["search"], "mode": "delay", "seconds": 2}` → 204 | From now on, the provider answers the listed methods normally, at normal cost, after waiting `seconds` (a number, more than 0 and at most 10). `none` clears it. A method has one fault at a time; setting another replaces it |
| `POST /_mock/weather` `{"on": true}` → 204 | Turns the weather on or off. While it is on, the n-th call to a provider since the last reset answers 429, at cost 0, when `sha256(f"{seed}:{provider}:{n}")` falls below the provider's `rate_limit` in `traits.json`. A scripted fault on the method takes precedence |
| `GET /_mock/log` | `{"calls": [...]}`, every provider call since the last reset, in order |
| `GET /_mock/health` | `{"status": "ok"}`; needs no token |

Every 429 the mock gives follows the rate limits of `stage-2.md`. Two calls are the same call
when they have the same provider, method and request body, compared as canonical JSON (key
order and whitespace do not matter); a research run's polls are never refused. A call made
again less than one second after a 429 for it is answered 429 again, whatever the faults and
the weather say. A call that has been answered 429 three times in a row is answered normally
on its next attempt, whatever the faults and the weather say, so a permanent `rate_limit`
answers 429, 429, 429, then once normally, and so on. Opening a browser session beyond the
cap of 4 is the exception: it is answered 429 for as long as 4 sessions stay open.

The mock starts in epoch 0 with no faults and the weather off. Each call log entry:

```json
{"seq": 1, "provider": "nimble", "method": "search", "depth": "lite",
 "query": "acme-robotics.test", "max_results": 10, "fields": null, "urls": [],
 "session": null, "cost": 1, "status": 200,
 "served": [{"url": "https://acme-robotics.test/about", "text": "..."}]}
```

`method` is `search`, `extract`, `research`, `session` (opening a browser session), `load` (a
page served to a session) or `browse` (an agent run); a Nimble extract with `render` is an `extract`, and an `extract` fault refuses it too. `depth` is `lite`, `fast` or `deep` for a Nimble or Tavily search and null
otherwise. `max_results` is the number of results a search asked for
(`max_results`), null when the request has none and for
other methods. `fields` is, for a research run, the sorted property names of the request's output
schema, and null when the request has no schema and for other methods. Both are recorded for
a faulted call too. `urls` lists the URLs an extract call asked for, and the URL of a load.
`session` is the browser session's id for a `session` or `load` entry, and null otherwise.
`served` lists every text the call returned: each snippet, truncated body or full text for a
search, each page for an extract, each citation excerpt for a research run, the page's text for a load and an agent run. A research run is
one entry, made when the run is created; its polls are not logged.
