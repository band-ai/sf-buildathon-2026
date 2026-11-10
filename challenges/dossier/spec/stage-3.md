# Dossier — Stage 3: change over time

The requirements from stages 1 and 2 continue to apply, with the additions below.
Numbered section references such as §4 and §8 refer to `stage-1.md`.

Companies change, and the web changes with them: a refresh may be served pages that earlier
builds were not, and may no longer be served pages they were. Sources also correct
themselves. A dossier now keeps the history of each field, answers as it stood at an earlier
time, and publishes its changes in a feed. It also names the company's executives.

The following applies to all operations, in addition to the earlier lists:

4. Every change to a selected value appears exactly once in the change feed, at the time this
   stage assigns to it.

## Two times per value

Every candidate and every selected value now has two times:

- **`true_from`**: the date from which the evidence says the value holds. A page states it
  in the header line `Effective: <YYYY-MM-DD>`. A page with no valid `Effective` line takes
  the date part, in UTC, of its `published_at`; with neither, `true_from` is null.
- **`learned_at`**: when this service first had the value. For a candidate, it is the time
  (§8, Builds) of the first build that gathered a candidate with the same field, value, URL
  and provider. For a selected value, it is the time of the build that made it the
  selected value.

Candidates gain `true_from` and `learned_at`. `retrieved_at` (stage 2) stays the time of the
build that gathered the candidate in the current candidate set. A selected value's
`true_from` is that of its selected candidate.

Each field of `GET /dossiers/{domain}` also carries the selected value's `true_from` and
`learned_at`. Both are null when the field is `unknown`. In an `as_of` response these
describe the selected value at that snapshot, using no later history.

The selection rule in `stage-2.md` is unchanged.

## Executives

A dossier has a seventh field, `executives`. The `fields` of every response that lists a
dossier's fields hold it, after the six fields of §4. A research run (§4) still asks for the
six fields of §4 only.

Its value is an array with one object `{ "title": T, "name": N }` for each title below that
has a selected person, in the order `cfo`, `coo`, `cto`. These objects are the field's
**members**. When no title has a selected person, the value is null and the field is
`unknown`.

For Appendix A, each title is a field with these statement phrases and with the format and
normalisation of `ceo` (A.4, A.5), the title's own statement phrases taking the place of
those for `ceo`:

| Title | Statement phrases |
|---|---|
| `cfo` | `chief financial officer`, `CFO` |
| `coo` | `chief operating officer`, `COO` |
| `cto` | `chief technology officer`, `CTO` |

A candidate of `executives` is a candidate of one title: it carries `title` beside `value`,
and its `value` is the person's name. A research claim is never a candidate of
`executives`.

```json
{ "value": [ { "title": "cfo", "name": "Ana Silva" }, { "title": "cto", "name": "Ben Okafor" } ],
  "status": "known", "true_from": "2025-09-01", "learned_at": "2026-03-01T09:00:00+00:00",
  "citations": [ { "url": "https://acme-robotics.test/team",
                   "excerpt": "Ana Silva is the chief financial officer of Acme Robotics.",
                   "provider": "nimble" },
                 { "url": "https://bizdata.test/acme-robotics",
                   "excerpt": "Acme Robotics CTO: Ben Okafor.", "provider": "tavily" } ],
  "candidates": [ { "title": "cfo", "value": "Ana Silva", "...": "...", "selected": true },
                  { "title": "cto", "value": "Ben Okafor", "...": "...", "selected": true } ] }
```

The selection rule in `stage-2.md` runs separately over the candidates of each title.

- `selected` is true on the highest-ranked candidate of each title that has candidates, and
  false on the others.
- `candidates` lists every candidate by title, in the order above, then in rank order.
- `citations` are, for each member in order, the `url`, `excerpt` and `provider` of every
  candidate with the member's title and name, in rank order.
- `status` is `unknown` when the value is null, `contested` when the candidates of some
  title carry two or more different names, and `known` otherwise.
- A candidate's `learned_at` is the time of the first build that gathered a candidate with
  the same title, name, URL and provider.
- A member's `true_from` is that of its title's selected candidate. The field's `true_from`
  is the latest of its members' `true_from`, or null when any member's is null.
- `GET /dossiers/{domain}/values` chooses each title's person from the candidates at
  `true_at` and gives the value, `true_from` and `citations` from them by these rules.

A history and feed entry for `executives` is typed by title, in place of the table in
Changes and corrections. A title **differs** between the earlier and the new value when
exactly one of them has a member with that title, or both have one and their names differ. A
differing title counts as a correction when both values have a member with that title, both
members' `true_from` are not null, and the new member's is on or before the earlier
member's. The entry is `correction` when every differing title counts as a correction, and
`change` otherwise.

The `data-testid` attributes of the screens in `stage-2.md` name only the six fields of §4:
`executives` takes none of them, and a screen that shows it does so with other markup. On
`/contested`, "no field is contested" means none of those six fields is.

## Changes and corrections

When a build completes `ready`, each field whose selected value differs from its selected
value before the build gets one history entry, and one feed entry, of one of two types:

| Type | When |
|---|---|
| `correction` | Both the earlier and the new value are not null, and the new value's `true_from` is on or before the earlier value's `true_from` |
| `change` | Every other difference, including a value appearing where there was none, a value disappearing, and either `true_from` being null |

A field's first selected value, set by the dossier's first build that completes `ready`,
gets a history entry of type `initial` and no feed entry. A field that is `unknown` after
that build gets its first entry when it first gets a value, and that entry is a `change`.

A build that completes with the same selected value for a field adds nothing for it, even
when its candidates, citations or `true_from` differ. A `failed` build adds nothing. Concurrent refreshes
of one dossier run one build (§8) and so add each entry once.

## `GET /dossiers/{domain}?as_of=`

```http
GET /dossiers/acme-robotics.test?as_of=2026-03-15T00:00:00+00:00
```

Returns the dossier as this service had it at `as_of`: the fields, candidates and
`researched_at` of the latest build that completed `ready` and whose time is at or before
`as_of`, decided by `learned_at`, never by `true_from`. `state` is `ready`. `spent_units` is
the total of the builds whose time is at or before `as_of`.

When several ready builds have the same time, return the last of them in build order.
This also applies when equivalent RFC 3339 timestamps use different offsets. The clock
need not advance between builds.

| Case | Response |
|---|---|
| `as_of` is not an RFC 3339 timestamp with an explicit offset | 422 `validation_failed` |
| No build of the dossier completed `ready` with a time at or before `as_of` | 404 `not_found` |
| No dossier for the domain | 404 `not_found` |

Without `as_of`, `GET /dossiers/{domain}` is unchanged.

## `GET /dossiers/{domain}/values?true_at=`

```http
GET /dossiers/acme-robotics.test/values?true_at=2025-06-01&as_of=2026-04-01T09:00:00+00:00
```

Returns, for each field, the value that the evidence this service had at `as_of` says held
on the date `true_at`. `as_of` defaults to the current time (§8).

A **page version** is what one ready build gathered from one URL: its candidates and its
`true_from`. The versions of a URL known at `as_of` are those gathered by ready builds whose
time is at or before `as_of`, taken in build order. Each version holds from its `true_from`.
When a later version of the same URL is gathered, it replaces every earlier version of that
URL whose `true_from` is on or after its own. The latest earlier version that it does not
replace stops holding on the later version's `true_from`. A version whose `true_from` is
null holds from no date, and a later version with a null `true_from` replaces every earlier
version of its URL. A gathered version with no candidates still replaces or ends earlier
versions by this rule.

The candidates **at `true_at`** are those of every version that holds on that date. Each
field's value is chosen from them by the selection rule in `stage-2.md`, and its
`true_from` is that of the chosen candidate.

```json
{ "domain": "acme-robotics.test", "true_at": "2025-06-01",
  "as_of": "2026-04-01T09:00:00+00:00",
  "fields": { "ceo": { "value": "Dana Ruiz", "true_from": "2021-04-01",
                       "citations": [ { "url": "...", "excerpt": "...", "provider": "nimble" } ] },
              "...": "..." } }
```

A field with no candidate at `true_at` has `"value": null`, `"true_from": null`,
`"citations": []`. Citations are those of the candidates at `true_at` with the chosen value.

| Case | Response |
|---|---|
| `true_at` missing or not a `YYYY-MM-DD` date, or `as_of` not an RFC 3339 timestamp with an explicit offset | 422 `validation_failed` |
| No dossier for the domain, or no build of it completed `ready` with a time at or before `as_of` | 404 `not_found` |

For state imported from an export, the builds and versions are those Upgrades gives.

## `GET /dossiers/{domain}/history`

```json
{
  "domain": "acme-robotics.test",
  "fields": {
    "ceo": [
      { "type": "initial", "value": "Dana Ruiz", "true_from": "2021-04-01",
        "learned_at": "2026-03-01T09:00:00+00:00",
        "citations": [ { "url": "...", "excerpt": "...", "provider": "nimble" } ] },
      { "type": "change", "value": "Lee Park", "true_from": "2026-03-20",
        "learned_at": "2026-04-01T09:00:00+00:00",
        "citations": [ { "url": "...", "excerpt": "...", "provider": "tavily" } ] }
    ],
    "legal_name": [ { "...": "..." } ],
    "hq_city": [],
    "founded_year": [ { "...": "..." } ],
    "headcount_range": [ { "...": "..." } ],
    "funding_total": [ { "...": "..." } ],
    "executives": [ { "...": "..." } ]
  }
}
```

- `fields` holds all seven fields. Each list is in the order the entries were added, oldest
  first.
- An entry's `value`, `true_from`, `learned_at` and `citations` are those of the selected
  value it records. An entry whose value is null has `"true_from": null` and
  `"citations": []`.
- No dossier for the domain is 404 `not_found`.

## `GET /changes`

```http
GET /changes?since=0&limit=50
```

```json
{
  "changes": [
    { "seq": 1, "domain": "acme-robotics.test", "field": "ceo", "type": "change",
      "from": "Dana Ruiz", "to": "Lee Park", "true_from": "2026-03-20",
      "learned_at": "2026-04-01T09:00:00+00:00" }
  ],
  "has_more": false
}
```

The feed holds every `change` and `correction` entry of every dossier.

- `seq` is a positive integer, unique across the feed, and larger for every later entry.
  Entries added by one build are numbered in the order of the fields in `stage-1.md` §4,
  then `executives`.
- `from` and `to` are the earlier and the new selected value, either of which may be null.
  `true_from` is the new value's. `learned_at` is the time of the build that added the
  entry.
- `since` defaults to 0 and lists only entries whose `seq` is greater than it. It is an
  integer, 0 or more. Entries are ordered by `seq` ascending.
- `limit` defaults to 50, range 1 to 200. `has_more` is true when entries exist beyond the
  last one returned.

## Upgrades

A stage-3 service must accept an export produced by the same team's stage-1 or stage-2
service. Every imported field that has a value gets one history entry of type `initial`,
with `learned_at` the dossier's `researched_at` and `true_from` null unless the exported
state records the dates that give it. The feed starts empty; the first build after import
compares its selected values with the imported ones. Existing tokens, dossiers and completed
idempotent responses survive the import as in `stage-1.md` §10, and the history and feed
of a stage-3 export survive a stage-3 import unchanged. So do its builds: after a
stage-3 import, `?as_of=` and `/values` answer as they did in the exporting service.

State imported from a stage-1 export counts as one build that completed `ready` at the
dossier's `researched_at`, and each imported candidate's URL as one version gathered by it;
imported candidates have `learned_at` equal to their `retrieved_at`. An `as_of` at or after
that time and before the next build returns the imported fields, and an earlier `as_of` is
404 `not_found`. An imported dossier whose `researched_at` is null answers every `as_of` with
404 `not_found` until a build completes.

State imported from a stage-2 export keeps the builds that the stage-2 service made, each
with its time, its outcome and its spending. Each of them that completed `ready` keeps the
candidates it gathered and, for each URL it gathered, one page version whose `true_from`
follows from that page's `Effective` and `Published` lines as that build gathered them
(Two times per value). State that the stage-2 service had itself imported counts as one
build that completed `ready` at the dossier's `researched_at`. `?as_of=`, `/values` and each
candidate's `learned_at` then answer as if this service had made those builds. History is
still one `initial` entry per field that has a value, as above, and an `as_of` response takes
each field's `learned_at` and `true_from` from that history (Two times per value).

An export of a stage-1 or stage-2 service has no `executives` candidates. After its import,
`executives` is `unknown`, in the imported state and in every build kept from the export,
and has no history entry; the first build that completes `ready` with a value for it adds a
`change`, or an `initial` entry when it is the dossier's first build that completes `ready`.

## Concurrency

Concurrent refreshes and reads must produce the same results as executing them one at a time
in some order. No change appears twice in the feed, and none is missing from it.

## Restarts

This row replaces the Disk row of the resource limits in `stage-1.md` §2:

| Limit | Value |
|---|---|
| Disk | the container's filesystem; it survives a container restart |

The container may be stopped abruptly at any time, with no warning and no time to finish what
the service is doing, and then started again. The sentence "State need not survive an
abrupt container restart" in `stage-1.md` §10 no longer applies. When no build is running
at the stop, the service answers after the restart exactly
as it did before the stop:

- Every account signs in with its password, and every bearer token is valid.
- Every dossier answers `GET /dossiers/{domain}`, with and without `as_of`,
  `GET /dossiers/{domain}/values` and `GET /dossiers/{domain}/history` as before, and
  `GET /dossiers` lists the same dossiers.
- The change feed holds the same entries with the same `seq`. An entry added after the
  restart has a larger `seq` than every entry before it.
- A replay of a completed idempotent request answers as §7 requires.
- The clock reads the time it read before the stop until reset or `POST /_test/clock` moves
  it.
