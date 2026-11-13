# Dossier — Stage 4: independent sources, batches and provider failure

All requirements from stages 1–3 continue to apply, with the additions below. Numbered section
references such as §4, §8 and §9 refer to `stage-1.md`.

Many URLs can carry one source: copies, syndicated articles and lookalike domains. A dossier
now says which independent origins stand behind each value, and who has invested in the
company. Researchers submit companies in batches under one shared budget, and research
continues when provider calls fail. There are three idempotent write paths: stage 1's two
and `POST /batches`.

The following applies to all operations, in addition to the earlier lists:

5. Spending never exceeds a budget that this specification or the caller sets.

## Lineage header lines

Three header lines (§4, Pages) now carry requirements:

| Header line | Meaning |
|---|---|
| `Registrant: <domain>` | The domain whose owner publishes the page |
| `Canonical: <URL>` | The page is a copy; the URL is the original |
| `First-Published-By: <domain>` | The page republishes material first published by that domain |

Domains in these lines, and the host of a `Canonical` URL, are normalised as in §4. A page
with no valid `Registrant` line has the host of its own URL, normalised, as its registrant.

## Own pages

A page counts as kind `own` for a company only when its registrant is the company's domain.
Any other page that states `Kind: own` has kind `aggregator` for the selection rule in
`stage-2.md`, and its candidates report `"kind": "aggregator"`.

A page that states `Kind: own` and whose registrant is not the host of its own URL,
normalised, is a **lookalike**: a site presenting itself as a company it is not registered
to.

## Origins

Every page has one **origin**, a domain, taken from the first of these that applies:

1. Its `First-Published-By` domain.
2. When its `Canonical` URL is not the page's own URL, the origin of the page at that URL
   (its **original**), by these same rules.
3. The company's domain, when the page is a lookalike.
4. Its registrant.

A build obtains from a provider each original that rule 2 needs. From the page whose origin
is sought, rule 2 follows at most three `Canonical` URLs in a row. Where it would follow a
fourth, or where no provider serves a page at the URL, the host of that URL takes the place
of the original's origin.

Pages with the same origin are one source, however many URLs, providers or kinds they have.

Candidates gain `origin`, the origin of their page. Each field gains three keys:

```json
{ "value": "Dana Ruiz", "status": "known",
  "citations": [ { "...": "..." } ], "candidates": [ { "...": "...", "origin": "acme-robotics.test" } ],
  "origins": ["acme-robotics.test", "registry.test"],
  "corroborated": true, "corroborated_since": "2026-03-01T09:00:00+00:00" }
```

- `origins` lists the distinct origins of the candidates whose value is the selected value,
  sorted ascending. It is `[]` for an `unknown` field.
- `corroborated` is true when `origins` has two or more entries, otherwise false.
- `corroborated_since` is the time (§8) of the earliest ready build after which the
  selected value has had two or more **standing origins**, or null while it has fewer.
  The standing origins of a selected value are the origins of every candidate with that
  value that any ready build has gathered since the value became the selected value (the
  `learned_at` of its latest history entry, stage 3), whether or not a later build
  gathered it again. A new selected value starts with none. Imported candidates count as
  gathered at the imported `researched_at`. When a stage-3 export is imported, the candidates
  of each of its builds count as gathered at that build's time.

Imported candidates whose export records no origin take the host of their URL, normalised,
as their origin.

For `executives` (`stage-3.md`) and `investors` (below), these keys follow the field's
members. A member's candidates are those with its title and name (`executives`) or with its
name (`investors`).

- `origins` lists the distinct origins of the candidates of all members, sorted ascending.
  It is `[]` for an `unknown` field.
- `corroborated` is true when the candidates of every member have two or more distinct
  origins, and false otherwise, including for an `unknown` field.
- `corroborated_since` is the time of the earliest ready build after which every member has
  had two or more standing origins, or null while some member has fewer or the field is
  `unknown`. A member's standing origins are the origins of every candidate of that member
  that the build after which it last became a member, or any later ready build, has
  gathered, whether or not a later build gathered it again. Imported candidates count as
  above.

## Investors

A dossier has an eighth field, `investors`. The `fields` of every response that lists a
dossier's fields hold it, after `executives`, and the feed entries one build adds are
numbered with `investors` last.

For Appendix A, `investors` is a field with the statement phrases `investor`, `investors`,
`led by`, `backed by` and `participated`. Occurrences of the company's name and of these
statement phrases are first taken out of the sentence and separate the words around them.
Of the runs of capitalised words (A.4) joined by single spaces that remain, each not part of
a longer such run, a run of two or more words whose last word is `Ventures`, `Capital`,
`Partners`, `Fund`, `Investments`, `Holdings` or `Equity` is an **investor name**. In an
excerpt that contains an amount (A.4), the run that starts directly after `led by` or
`backed by` and one space is an investor name too, whatever its length and last word:
`Acme Robotics raised $40M in a round led by General Atlantic.` names `General Atlantic`,
and `Acme Robotics is led by Dana Ruiz.` names no investor. An
investor name normalises to the text as the excerpt writes it. Rules 1 to 4 of A.2 apply;
in place of rule 5, an excerpt supports each investor name it contains.

The `value` of a candidate of `investors` is one investor name. A research claim is never a
candidate of `investors`.

An investor name is a **member** when, among the field's candidates, one with that name has
`kind` `own` or `filing`, or those with that name have two or more distinct origins.

In place of the selection rule in `stage-2.md`, the value is the array of the members'
names, sorted by Unicode code point, or null when there is no member. `investors` is `known`
exactly when it has a member, and `unknown` otherwise, in place of the rules that make a
field `known` exactly when the evidence supports a value for it.

```json
{ "value": ["Bluebird Capital", "Northwind Ventures"], "status": "known",
  "true_from": "2024-05-02", "learned_at": "2026-03-01T09:00:00+00:00",
  "citations": [ { "...": "..." } ],
  "candidates": [ { "value": "Bluebird Capital", "...": "...", "selected": true }, { "...": "..." } ],
  "origins": ["acme-robotics.test", "dealwire.test", "registry.test"],
  "corroborated": true, "corroborated_since": "2026-03-01T09:00:00+00:00" }
```

- `selected` is true on every candidate whose name is a member, and false on the others.
- `candidates` lists every candidate in the order the selection rule in `stage-2.md` ranks
  them.
- `citations` are, for each member in the order of the value, the `url`, `excerpt` and
  `provider` of every candidate with its name, in rank order.
- A member's `true_from` is the earliest `true_from` that is not null among the candidates
  with its name, or null when all of them are null. The field's `true_from` is the latest of
  its members' `true_from`, or null when the value is null or any member's is null.
- `GET /dossiers/{domain}/values` decides membership from the candidates at `true_at` and
  gives the value, `true_from` and `citations` from them by these rules.

A history and feed entry for `investors` is typed by name, in place of the table in
`stage-3.md` Changes and corrections. A name in the new value and not in the earlier one
counts as a correction when its `true_from` and the earlier value's `true_from` are both not
null and its `true_from` is on or before the earlier value's. The entry is `correction` when
every name in exactly one of the two values counts as a correction, and `change` otherwise.

The screens treat `investors` as `stage-3.md` treats `executives`: it takes none of the
`data-testid` attributes of `stage-2.md`, and "no field is contested" on `/contested` means
none of the six fields of §4 is.

## Batches

`POST /batches` starts builds, and so joins `POST /dossiers` and
`POST /dossiers/{domain}/refresh` as a request that makes provider calls (§8, Builds).

A batch researches several companies under one shared budget. A batch belongs to the user who
created it; another user's batch is 404 `not_found`.

### `POST /batches`

**An idempotent write path.** `Idempotency-Key` is required; see §7.

```http
POST /batches
Idempotency-Key: 5d02e1...

{ "domains": ["acme-robotics.test", "brightgear.test"], "budget_units": 200 }
```

```json
202
{ "batch_id": "b_2", "state": "running", "budget_units": 200, "spent_units": 0,
  "dossiers": [ { "domain": "acme-robotics.test", "state": "building" },
                { "domain": "brightgear.test", "state": "ready" } ] }
```

| Case | Response |
|---|---|
| `domains` missing, empty or longer than 50 entries | 422 `validation_failed` |
| An entry of `domains` invalid after normalisation (§4) | 422 `validation_failed` |
| Two entries of `domains` the same after normalisation | 422 `validation_failed` |
| `budget_units` missing, not an integer, below 1 or above 100000 | 422 `validation_failed` |

A `budget_units` that is not an integer is 422 `validation_failed` whatever its JSON type: a
string, `true` or `1.5` included. The row above takes precedence over the 400
`malformed_request` of §5 for a field of the wrong JSON type.

- `dossiers` lists the normalised domains in the order given, each with its dossier's state.
- A domain with no dossier gets one, and the batch runs its first build. A domain that
  already has a dossier is not researched by the batch and costs it nothing.
- `spent_units` is the total cost (§9) of the provider calls the batch's builds made. It never
  exceeds `budget_units`. Each build in a batch still spends at most 80 units, and its cost
  also counts in its dossier's `spent_units`.
- When the budget would be exceeded by a further call, the batch makes no more provider calls,
  and its remaining builds complete with the pages and research claims they have obtained:
  each of their fields is `known` exactly when those support a value for it.

### `GET /batches/{id}`

Returns the batch in the shape above. `state` is `running` while any of its builds runs, then
`done`. Unknown batch is 404 `not_found`.

## Provider failure

A provider may answer a call with an error (any 5xx status, or 429). The build continues: it
may make the same request again, through that provider or another.

- A build in which every call to one or more providers fails, while `nimble` answers,
  completes `ready`, with every field `known` that the evidence (§4) reachable through the
  providers that answer supports.
- A build in which every research run fails, while searches and extracts are answered,
  completes `ready`, with every field `known` that the evidence reachable by search and
  extract supports.
- A build in which every call to every provider fails completes `failed` (§8), within the
  time bound of §8.
- A call a provider refuses with an error status costs nothing (§9).

## Restarts

The restart requirements of `stage-3.md` hold for batches as for the rest of the state. When
builds are running at the stop, everything else is still answered as before the stop, and
each build that was running:

- Does not stay `building`. It ends `ready` or `failed` within 10 seconds of `GET /health`
  first answering 200 after the restart, when each provider call it makes after the restart
  answers within one second. It may end `failed` although some of its calls succeeded; it
  then leaves the fields as they were (§8).
- Is one build across the restart: its calls before and after the stop together spend at
  most 80 units (§9), and a batch's builds together never spend more than its
  `budget_units`.
- Has every unit a provider billed for its calls, before and after the stop, counted in its
  dossier's `spent_units` and, for a batch's build, in the batch's `spent_units`. They may
  also count calls that were in flight at the stop and that no provider billed.

After the restart, `POST /dossiers/{domain}/refresh` starts a new build of each such dossier
as it does for any other.

## Upgrades

A stage-4 service must accept an export produced by the same team's stage-1, stage-2 or stage-3
service, preserving dossiers, candidates, history, the change feed and completed idempotent
responses as in `stage-1.md` §10. A stage-3 export keeps its
builds: after the upgrade, `?as_of=` and `/values` answer from them as the stage-3 service did,
with the keys this stage adds. Citations carried in the
imported state remain citations served to this service.

An export of a stage-1, stage-2 or stage-3 service has no `investors` candidates. After its
import, `investors` is `unknown`, in the imported state and in every build kept from the
export, and has no history entry; the first build that completes `ready` with a value for it
adds a `change`, or an `initial` entry when it is the dossier's first build that completes
`ready`.
