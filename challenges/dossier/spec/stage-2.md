# Dossier — Stage 2: competing sources and the dossier screens

The stage-1 requirements continue to apply, with the additions below. Numbered section
references such as §4 and §7 refer to `stage-1.md`.

Sources disagree. A dossier now keeps every value its evidence supports, as candidates, and
selects one per field by a fixed rule. Researchers read dossiers, their evidence and the
fields in dispute in a browser.

The following applies to all operations, in addition to the stage-1 list:

3. A field's selected value is the one the selection rule below picks from the field's
   candidates; the same candidates always yield the same value.

## Page kind and publication time

Two header lines (§4, Pages) now carry requirements:

| Header line | Meaning |
|---|---|
| `Kind: own`, `Kind: filing`, `Kind: news`, `Kind: aggregator` | The page's **kind**: the company's own site, a filing registry, a news report, or an aggregator of company data |
| `Published: <RFC 3339 timestamp>` | When the page was published |

A page with no `Kind` line, or with a value not listed above, is of kind `own` when the
host of its URL, normalised as `stage-1.md` normalises a domain, is the company's domain,
and of kind `aggregator` otherwise. A page with no `Published` line, or with a value that is not an RFC 3339 timestamp, has no
publication time.

## Page text

From this stage, a page's **text** is the text a browser shows once the page has loaded,
without clicking controls. Activating disclosure controls is not required. The graded
corpus contains no facts that require a click to reveal them.
Evidence (§4) is read from page text so defined, and a citation's excerpt must appear in the
page's text. A citation's `provider` is the provider that served the text the excerpt was
copied from.

## Web access

From this stage an extract through `nimble` may ask Nimble to load the page in a browser and
serve the text the browser shows once the page has loaded, with no control activated:
`provider_options={"render": True}` on WebRouter's extract.

Two optional browser vendors are also available, in addition to the providers in §2:

- `kernel`, through `open_browser`;
- `browserbase`, through `open_browser` and `browse`.

A service may use Nimble's rendered extract alone to obtain every page's browser text;
neither browser vendor is required.

The deployment provides these environment variables in addition to those in §2:

| Variable | Meaning |
|---|---|
| `KERNEL_API_KEY` | Credential for the `kernel` provider |
| `KERNEL_BASE_URL` | Base URL of the `kernel` provider endpoint |
| `BROWSERBASE_API_KEY` | Credential for the `browserbase` provider |
| `BROWSERBASE_BASE_URL` | Base URL of the `browserbase` provider endpoint |

WebRouter reads the keys from the environment. A service that uses these vendors passes their
base URLs to WebRouter in `provider_config`, beside those of §2:

```python
provider_config={"kernel": {"base_url": <KERNEL_BASE_URL>},
                 "browserbase": {"base_url": <BROWSERBASE_BASE_URL>}}
```

These calls cost, in the units of §9:

| Call | Cost |
|---|---|
| Extract through `nimble` that loads the page in a browser | 3 per URL requested, including a URL for which no page is returned |
| Open a session through `kernel` | 0 |
| Open a session through `browserbase` | 2 |
| Each page served to a session, through either | 1 |
| Browse run through `browserbase` | 4 |

A failed open, a failed page load and releasing a session cost nothing.

Each provider keeps at most 4 sessions open at once; opening another is answered with an
error. A session that no client has been connected to for 60 seconds is closed by the
provider.

## Rate limits

From this stage a provider may answer any call with 429. A call answered 429 costs nothing
(`stage-1.md` §9). The same call (the same provider, operation and arguments) made again less
than one second after a 429 for it was answered is answered 429 again. No call is answered
429 more than three times in a row, except that opening a session while its provider keeps
4 open (Web access) is answered 429 until one of them closes. Time a build spends waiting to
make a call again after a 429 does not count toward the 10 seconds of `stage-1.md` §8.

## Candidates

A **candidate** is one value for one field, supported by one excerpt of one page. Every
value that a page of the evidence (§4) supports for a field is a candidate of that field,
once for each such page. The evidence now also holds the page that each research claim of
the evidence cites, whether or not the citation supports its claim: a build reads that page
as it reads any other. A research claim whose citation does not support it is still not a
candidate. A candidate's `provider` is a provider that served the text
its excerpt is taken from; when several did, any of them may be given.

Each field gains `candidates`:

```json
{
  "value": "Dana Ruiz",
  "status": "contested",
  "citations": [ { "url": "https://acme-robotics.test/about", "excerpt": "...", "provider": "nimble" } ],
  "candidates": [
    { "value": "Dana Ruiz", "url": "https://acme-robotics.test/about",
      "excerpt": "Dana Ruiz has led Acme Robotics as chief executive since 2021.",
      "provider": "nimble", "kind": "own",
      "published_at": "2026-01-10T00:00:00+00:00",
      "retrieved_at": "2026-03-01T09:00:00+00:00", "selected": true },
    { "value": "Sam Ortiz", "url": "https://bizdata.test/acme-robotics",
      "excerpt": "Acme Robotics CEO: Sam Ortiz.",
      "provider": "tavily", "kind": "aggregator",
      "published_at": "2026-02-20T00:00:00+00:00",
      "retrieved_at": "2026-03-01T09:00:00+00:00", "selected": false }
  ]
}
```

- `url`, `excerpt` and `provider` follow the citation rules in §4.
- `kind` is the page's kind, and `published_at` its publication time or null. Only an
  imported candidate (below) has a null `kind`; it has the authority of `aggregator`.
- `retrieved_at` is the time of the build that gathered the candidate (§8, Builds).
- `selected` is true on exactly one candidate of a field that has candidates, the one the
  rule picks, and false on the others.
- `candidates` lists the candidates of the last build that completed `ready`, in the order
  the selection rule ranks them, the selected one first. A field with no candidate has
  `"candidates": []` and is `unknown`.
- Two values are the same value when they are equal as JSON values; strings are compared
  exactly, after removing surrounding whitespace.

## The selection rule

Rank a field's candidates, highest first, by:

1. **Authority** of the page's kind: `own` and `filing` rank equal and highest, then `news`,
   then `aggregator`.
2. **Recency** within the same authority: the later `published_at` ranks higher. A candidate
   without a publication time ranks below every candidate of the same authority that has one.
3. **URL**: when authority and publication time are equal, the candidate whose `url` is
   smaller, comparing the strings by Unicode code point, ranks higher; between two
   candidates with the same URL, they rank by provider in the order `nimble`, `tavily`,
   `kernel`, `browserbase`.
4. **Value**: between two candidates with the same URL and provider, the one whose value is
   smaller ranks higher: integers compare as numbers, strings by Unicode code point after
   removing surrounding whitespace.

The highest-ranked candidate is the selected one. The field's `value` is the selected
candidate's value, and its `citations` are the `url`, `excerpt` and `provider` of every
candidate with that value, in rank order.

A candidate of lower authority is selected only when no candidate of higher authority
exists for that field. The rule runs over all of a field's candidates.

## Status

`status` is now one of three values:

| `status` | When |
|---|---|
| `known` | The field has candidates, and they all have the same value |
| `contested` | The field's candidates carry two or more different values |
| `unknown` | The field has no candidate; `value` is null |

A `contested` field still has a selected `value` and its citations.

`GET /dossiers` (§8) is unchanged. The `legal_name` it lists is the selected value.

## Screens

The following screens must be reachable by URL. Other screens must be reachable through the UI.
Server-side and client-side rendering are both permitted.

| Route | Screen |
|---|---|
| `/` | The dossier list with search, and a form to research a domain |
| `/dossiers/{domain}` | One dossier: its state, its six fields with their values, status and citations, a refresh and a reload |
| `/dossiers/{domain}/evidence` | Every candidate of every field of that dossier |
| `/contested` | Every contested field across all dossiers |
| `/signup` | Signup |
| `/login` | Login |

The browser and the API share `/dossiers/{domain}`. Return the UI for `Accept: text/html`;
API requests without that header receive JSON. `/`, `/dossiers/{domain}/evidence` and
`/contested` are browser routes; they read the API's dossier data. The domain in a browser
route is normalised as in §4.

The UI must expose the `data-testid` attributes listed below for integration testing. Additional
elements are permitted, and the visual implementation is the team's choice subject to the
product-quality requirements below.

## Product and visual direction

The browser experience must feel like a coherent, presentation-ready research product, not a
thin wrapper of raw controls. Aim for a calm, legible, evidence-first character: a reader
opening a dossier should see at a glance which fields are known, which are unknown and which
are contested, and where each value came from.

A field's value and its status must be the clearest information on the dossier screen, with
its citations directly beside it. Fields, citations, candidates and contested fields should be
easy to scan, and status, provider, page kind and publication time should be understandable
without interpreting raw API data. Use a consistent visual system for typography, spacing,
colour, controls and feedback. Primary actions — research, refresh — must be easy to identify.
Known, unknown, contested, building, failed, loading, successful, refused and uncertain states
must be visually distinct as well as satisfying the behavioural requirements below. Format
names, years, headcount ranges, money and timestamps for people first; expose technical
identifiers only where they help the user. Each citation shows its excerpt as quoted text and
links to its URL.

The required flows must remain clear and usable at a 375 CSS-pixel viewport and at conventional
desktop widths, without horizontal page scrolling. Inputs need visible labels, keyboard focus must
be apparent, and text and controls need sufficient contrast. Provide considered empty, loading and
error states, and keep navigation consistent across the required routes. A custom illustration,
brand asset or exact visual match to a reference is not required.

## Signup and login

| `data-testid` | Element |
|---|---|
| `signup-email`, `signup-password`, `signup-display-name` | Inputs |
| `signup-submit` | Button |
| `login-email`, `login-password`, `login-submit` | Inputs and button |
| `auth-error` | Error message. Present only when there is one |
| `current-user` | Visible on every screen when signed in. Text contains the display name |
| `logout-button` | Button |

## Dossier list — `/`

| `data-testid` | Element |
|---|---|
| `research-domain` | Input for the domain to research |
| `research-submit` | Button. Sends `POST /dossiers` |
| `research-error` | Error message, when the request is refused — including an invalid domain |
| `research-uncertain` | Shown when the outcome of a research request is unknown (below) |
| `dossier-search` | Input. Filters the list as `q` does on `GET /dossiers` |
| `dossier-list` | Container. Children ordered by domain ascending |
| `dossier-item-{domain}` | One per listed dossier. Carries `data-state="{state}"`. Text contains the domain, and the legal name when known. Links to `/dossiers/{domain}` |
| `empty-dossiers` | Shown instead of the list when no dossier matches |

A research request that succeeds, with 202 or 200, opens `/dossiers/{domain}` for the
normalised domain. A domain that already has a dossier, including one created by another
client after this browser read the list, opens that dossier and starts no build.

## Dossier — `/dossiers/{domain}`

| `data-testid` | Element |
|---|---|
| `dossier-domain` | Text is exactly the normalised domain |
| `dossier-state` | Text is exactly `building`, `ready` or `failed` |
| `dossier-spent` | Formatted `spent_units`. Carries `data-units="{integer}"` |
| `dossier-researched-at` | Text contains `researched_at`, formatted. Absent when it is null |
| `field-{field}` | One per field, six in all, in the order of the table in `stage-1.md` §4. Carries `data-status="{status}"` |
| `field-value-{field}` | The formatted value. Carries `data-value` (below). Present only when the value is not null |
| `field-contested-{field}` | A marker. Present only when the field is `contested` |
| `field-citations-{field}` | Container of the field's citations, in API order |
| `citation-{field}-{n}` | The field's `n`th citation, counting from 1. Text contains the excerpt. Contains a link whose `href` is the citation's `url`. Carries `data-provider="{provider}"` |
| `dossier-evidence-link` | Link to `/dossiers/{domain}/evidence` |
| `dossier-refresh` | Button. Sends `POST /dossiers/{domain}/refresh` |
| `refresh-error` | Error message, when a refresh is refused |
| `refresh-uncertain` | Shown when the outcome of a refresh is unknown (below) |
| `dossier-reload` | Button. Reads the dossier again without starting a build |
| `dossier-not-found` | Shown instead of the fields when no dossier exists for the domain |

`data-value` is the API value as text: a string value unchanged, an integer in plain decimal
digits.

While the dossier's state is `building`, the screen reads the dossier again at least every
2 seconds until the state is `ready` or `failed`, and then shows the new fields without a
manual reload.

## Evidence — `/dossiers/{domain}/evidence`

| `data-testid` | Element |
|---|---|
| `evidence-{field}` | One container per field, six in all. Children in API `candidates` order |
| `candidate-{field}-{n}` | The field's `n`th candidate, counting from 1. Text contains the formatted value and the excerpt. Carries `data-value`, `data-provider`, `data-kind`, `data-url`, `data-published-at` (the RFC 3339 `published_at`, empty when null) and `data-selected="true"` or `"false"` |
| `evidence-empty-{field}` | Shown instead of candidates when the field has none |

## Contested fields — `/contested`

| `data-testid` | Element |
|---|---|
| `contested-list` | Container. Children ordered by domain ascending, then by field in the order of the table in `stage-1.md` §4 |
| `contested-item-{domain}-{field}` | One per contested field of any dossier. Carries `data-value` for the selected value. Text contains the domain, the field and every distinct candidate value. Links to `/dossiers/{domain}/evidence` |
| `empty-contested` | Shown instead of the list when no field is contested |

## Refresh and competing clients

After any successful action, the data on the same page must show the new state without a manual
reload. Navigation must wait for the write to succeed before it refreshes the data. Any mechanism
is fine, including a full navigation. Apart from the reading while a dossier is `building`,
there is no live-update requirement: another client may change state, but this browser need
only read again after its own action, an explicit reload or a build it is waiting on.

- `dossier-reload` reads the dossier again. **Latest read wins:** a delayed earlier read must
  not overwrite a later one, including when responses arrive out of order. This applies to the
  reads while a dossier is `building` as well.
- Another client may refresh a dossier after this browser reads it. A refresh from this
  browser while that build runs is answered 202 like any other and the screen follows the
  running build to its end.
- If a research or refresh response is lost, including after the request commits, show
  `research-uncertain` or `refresh-uncertain` (nonempty text), not `research-error` or
  `refresh-error`. Keep the request retryable with the **same key and body**. A successful
  retry removes both the error and the uncertainty elements, shows the dossier, and starts at
  most one build. Unknown outcomes are not confirmed refusals.

No background polling beyond the reading while `building`, live synchronization, or recovery
across page reloads is required.

## Existing clients after an upgrade

A stage-2 service must accept an export produced by the same team's stage-1 service. A browser
signed in before that export/import upgrade must remain signed in afterwards. Imported dossiers
appear in the list and on their screens. Each imported field gains one candidate for every
value that text the providers served to the dossier's last stage-1 build that completed
`ready` supports for that field (`stage-1.md` §4), once for each page whose served text
supports it. The candidate's excerpt is taken from that text and supports the value; its
`provider` is the provider that served that text, its `kind` and `published_at` are as the
exported state records them or else null, and its `retrieved_at` is the dossier's
`researched_at`. Each imported field's `value`, `status` and `citations` then follow from its
candidates by the selection rule and Status, as after a build. A research or refresh
request whose response was lost before export remains retryable after import with the same body and key; the UI must recover the original response
and show the imported dossier. These requirements apply when import completes between browser
requests; migration during an in-flight request is not required. No page reload or new screen
is required.

The candidates of an imported dossier are replaced by those of its next completed build.
