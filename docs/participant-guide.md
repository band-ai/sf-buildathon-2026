# Participant guide

Everything you need to compete: what to build, how to run your
band, and how to submit. This guide is the authoritative rules and instructions for
participants.

## What you build

A software factory in Band Desktop — a band of at least three distinct coding-agent
seats that plans work, implements it, hands off evidence and independently checks its
own results — and a service that factory builds. You give it a job and decide whether
to accept what comes back. What you submit is the factory, the room it worked in, and
the code it produced.

### The challenge

Dossier is a company-research service. A caller asks for a company by its web domain; the service researches it through Nimble, called through WebRouter, and keeps a dossier of six fields — legal name, headquarters city, CEO, founding year, headcount range and total funding raised — each with the excerpts that support it. Stage 3 adds a seventh field, the company's CFO, COO and CTO, and stage 4 an eighth, its investors. Stage 2 keeps every candidate value and selects one per field, reads a page's text as a browser shows it, and adds the browser screens; Kernel and Browserbase are optional browser vendors. Stage 3 adds history over two time axes and a change feed. Stage 4 counts independent origins rather than URLs, adds batches under a shared budget, and keeps research going when provider calls fail. Every scored check runs against a local mock web.

| Stage | What you build | Graded by |
|---|---|---|
| 1 | Company profiles researched through Nimble, called through WebRouter: six fields, each with the excerpts that support it, built in the background within a cost budget | API, citations, budget, concurrency and state transfer |
| 2 | Competing sources: every candidate kept, one selected by a fixed rule, and the browser screens | API, browser, client races and upgrades, plus stage 1 |
| 3 | Change over time: when a fact became true and when the service learned it, history, values as they held at a past date and a change feed; a seventh field, the CFO, COO and CTO | API, upgrades, concurrency and restarts, plus earlier stages |
| 4 | Independent origins, batches under a shared budget, provider failure and research economy; an eighth field, the investors | API, upgrades, restarts during builds and the economy workload, plus earlier stages |

**All four stages are released at kickoff.** There is nothing to wait for and nothing to
unlock. Work through them in order, because each one builds on the last.

`toy` is an unscored four-stage practice track with the same shape as the real ones. Run
it for easy practice — see [Practice on the toy](#practice-on-the-toy-example).

## What makes an entry count

### Eligibility

- At least three distinct coding-agent seats in Band Desktop, each with a mandate file
  that says which harness and model the seat runs. Seats may share a harness and a model.
- At least one complete output for stage 1.
- A submitted presentation, video and public GitHub repository as specified below. **The video shows
  your factory working** — the room, a handoff between seats, and the result it produced.
  Record the room in Band Desktop or in the Band console; either counts.
  A slideshow about the factory is not the same as the factory.

### The three rules that decide most entries

- **Hand-built code does not count.** A stage counts only if the code that passes its
  tests came out of a collaboration in your Band Desktop room. However green your tests
  are, code you wrote by hand does not count. Your room event log is what shows the work was
  the band's.

- **Code written to the tests disqualifies the entry.** You get part of each stage's
  checks, not the full set of tests. That is enough to wire your service up,
  but it's not meant to be a list of what will be run. Build to the specification, not the tests.
  See [Do not write to the tests](#do-not-write-to-the-tests) — this is the rule most likely
  to cost a team its entry, and it is enforced after submissions close.

- **Your mandates must be generic.** A mandate says how a seat works — what it owns, how
  it hands off, when it rejects. It must not name anything specific to your track: no
  endpoint paths, field names, or error codes. **A mandate that
  names track-specific detail disqualifies the entry** — see
  [Your mandates must be generic](#your-mandates-must-be-generic).

### Four gates. Fail any one and your entry is not ranked.

A failed gate is not a low score — it is a disqualified entry. `harness check` runs gates
1, 2 and the mandate half of gate 4 offline, so run it before you push.

1. Your roster lists **three or more distinct Band Desktop seat identities that you
   configured**, each with a mandate file named after that seat that names the seat's
   harness and model.
2. Your room log shows messages exchanged **between at least two of your own seats**,
   each addressing the other by `@handle`, with a reply in each direction.
3. `stage-1/` **builds and serves from a clean container** by following its `RUN.md`.
   Every other folder is judged the same way, but a folder that does not start costs
   that stage and the ones above it rather than the entry — see [Rubric](#rubric).
4. Your **mandates are generic** — they describe your factory, not this track — and
   your code is written to the spec rather than to the tests.

**Anything else `harness check` reports also keeps your entry out of the ranking:** a file
missing from the layout in [The repository you submit](#the-repository-you-submit), or a
file that looks like it holds a credential.

### Rubric

Every entry that passes the gates is judged on four criteria.

| Criterion | Weight | What judges look for |
|---|---|---|
| **Factory** | **40%** | **Generic:** another team could point your mandates at a different problem.<br>**Effective:** how far through the four stages it got with code that meets the spec, including what the shipped checks never asked.<br>**Reusable:** `FACTORY.md` and `mandates/` are enough to stand it up, and explain your design choices and what they cost, measured time and model spend, and how the factory catches and recovers from bad work |
| **App** | **20%** | What your factory built: a UI that is coherent, presentation-ready, responsive and clear in the states the stage-2 spec identifies, over code another developer could maintain |
| **Agent Teamwork** | **20%** | Your seats did the work together, and without you.<br>**Collaboration:** the seats really shared the work — more than one seat did it, review changed something, handoffs carried the whole task, and the code traces to the room.<br>**Autonomy:** in the run you submit, the task you dispatch for each stage is the only human input — no steering, approvals, debugging hints or reruns until it passed. Runs made while you developed the factory are not judged — see [Build and check each stage](#build-and-check-each-stage) |
| **Research economy** | **20%** | What the service spends on web research per correct field on a fixed stage-4 workload, compared with a fixed strategy benchmark |

We do not score chat volume, seat count or prompt length. What is read from the room log
is whether the work was **distributed** — one seat carrying 90% of it looks the same
however many messages it sent. Nor is manufactured conflict worth anything: a rejection
counts when it changed the work, and correct work that was accepted first time loses
nothing. [Agent Teamwork evidence](#agent-teamwork-evidence) says how to make sure the
evidence is there.

When two entries score the same, the one your band delivered faster ranks higher.
Delivery time is read from the room log: see [Agent Teamwork evidence](#agent-teamwork-evidence).

Use the presentation and video to explain your factory design, what it cost, a bad result
it caught, and the stage you reached. It does not replace `FACTORY.md`, which has to be
enough on its own for another team to stand your factory up.

## Prepare

Use Python 3.12+, Git, a running Docker daemon, a Band Desktop account,
and your own model-provider access. All seats may use the same
runtime/model, but can also use different harnesses or models.

Python is required here only to run the event harness. **Your submitted service may use
any language or framework.** Judges build your `Dockerfile` and communicate with the
container exclusively over HTTP. They do not import your source into Python or require
your compiler, interpreter, package manager or dependencies on the judge host. Install
everything your service needs while building the image and include its runtime in that
image. A TypeScript/Node, Go, Rust, Java or other implementation follows the same contract
and is judged the same way as a Python implementation.

Clone the kickoff repository, or extract the kickoff archive if you were given one.
Run commands below from its `sf-buildathon-2026/` directory:

```sh
python3.12 --version             # 3.12 or newer
docker --version                 # the daemon must be running
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r harness/requirements.txt
python -m playwright install chromium
python -m harness --help
```

The venv needs Python 3.12 or newer, so name that interpreter when you create it: the
`python3` that ships with macOS is 3.9, and `pip install` fails on it with `No matching
distribution found for playwright==1.63.0`. Inside the venv, `python` is the right one.

On Linux, browser system libraries may also be needed: `python -m playwright install
--with-deps chromium`. Isolated checks install the browser inside Docker. On Windows, run
these steps inside WSL2.

Keep the result repository separate from the challenge package and factory inputs:

```sh
mkdir -p ../band-work/result/stage-1 ../band-work/checks
git -C ../band-work/result init -b main
git -C ../band-work/result config user.name "Your Name"
git -C ../band-work/result config user.email you@example.test
```

`../band-work/` is only this guide's convention; the harness takes every path on the
command line, so use another location if you like and adjust the commands.
`../band-work/result` is your submission repository and `../band-work/checks` holds the
`harness run --out` directories you keep while iterating. Give your agents the absolute
path of the result repository: a seat works in its own sandbox, may not resolve
`../band-work`, and would otherwise create a repository only it can see.

The graded repository starts empty deliberately so the event does not choose an
implementation language for your factory. Configure Git names and emails for each seat.
The Python `scaffold/` is used by the toy walkthrough only; it is not part of any
challenge and need not be copied, translated or retained in a graded submission.

A Dossier service reaches the web through Nimble, called through WebRouter; how it must do that,
and the optional providers, are in `challenges/dossier/spec/stage-1.md` §2. The mock web that
stands in for every provider, and how to run it beside your service, is in
`challenges/dossier/web/README.md`, which also shows how to try a real company and why
`NIMBLE_BASE_URL` must be the real endpoint or unset, never empty. Stage 1 is API only; the
screens arrive in stage 2.
In Band Desktop, create at least three seats, each with its own seat identity. Confirm
that direct `@handle` messages reach each seat and that each seat can reply.

Prepare permissions for the result checkout, Git, Docker and browser checks. Keep
credentials outside the result repository and its Git history. Sandboxed seats and other
optional setup are in [Optional setup](#optional-setup).

## The repository you submit

Your entry to the hackathon is in the form of a github repository. The folder structure should
look like this:

```text
your-repo/
  README.md          team, track, and how to read this repository
  FACTORY.md         your factory: seats, design choices, costs, failure handling
  mandates/          one .md per seat, named after the seat, at least three; each
                     names the seat's harness and model
  room.json          the room, downloaded from Band — see Record the room
                     (or room-1.json … room-4.json, one per stage)
  dossier-runway.com.json
                     GET /dossiers/runway.com from your highest completed stage,
                     built against the live web — see below
  stage-1/ … stage-4/  one folder per stage you completed, holding its service's
                       Dockerfile, RUN.md and source
```

**Name each mandate after its seat as the room shows it**, ignoring case and punctuation:
`reviewer.md` for Reviewer, `delivery-manager.md` for Delivery Manager. Gate 1 checks that
every seat in your room log has a mandate file named after it. **Start each mandate with
the harness, model and effort that seat actually runs:**

```text
Harness: Claude Code
Model: claude-sonnet-5-5
Effort: high
```

Use the harness name as Band Desktop shows it (Claude Code, Codex, OpenCode, …) and the
exact model id. `harness check` reports a mandate that is missing either of those two lines.
Add `Effort:` when the harness has a reasoning-effort setting, with the level the seat runs
at as the harness names it. It is optional and not checked, but it tells judges and other
teams what your reported time and spend bought. Mandates must also be generic — see [Your mandates must be generic](#your-mandates-must-be-generic).

**Each stage folder is a complete, buildable service on its own, and it holds the
solution to that stage — not to a later one.** `stage-2/` is `stage-1/` carried forward
and extended; `stage-3/` is `stage-2/` carried forward, and so on. When you finish a
stage, have the band copy the folder and widen the copy to the next stage's spec.

A Dossier entry also commits **`dossier-runway.com.json`** at the top of the repository: the
`GET /dossiers/runway.com` response of your highest completed stage, saved verbatim, from a
build against the live web with your own Nimble key. The file is not scored, but
`harness check` checks it, and an entry without it is not ranked. Make it once that stage
folder is final, and again if you change the folder afterwards:

1. **Pick the folder.** It is the highest `stage-N/` for which
   `python -m harness run --track dossier --repo <repo> --all` prints `claimed stage: N`, with every folder below it
   claiming its stage too.
2. **Build it and start it.** Run this from the repository root, with `STAGE` set to that
   folder. `read` keeps your Nimble key out of the shell history; the other providers get
   placeholder keys, so only Nimble answers:

   ```sh
   STAGE=stage-4
   read -rs NIMBLE_API_KEY && export NIMBLE_API_KEY     # paste the key, then Enter
   docker build -t dossier-live $STAGE
   docker run -d --name dossier-live -p 8000:8000 -e PORT=8000 \
     -e NIMBLE_API_KEY -e NIMBLE_BASE_URL=https://sdk.nimbleway.com \
     -e TAVILY_API_KEY=unavailable -e TAVILY_BASE_URL=https://api.tavily.com \
     -e KERNEL_API_KEY=unavailable -e KERNEL_BASE_URL=https://api.onkernel.com \
     -e BROWSERBASE_API_KEY=unavailable -e BROWSERBASE_BASE_URL=https://api.browserbase.com \
     dossier-live
   until curl -sf http://localhost:8000/health > /dev/null; do sleep 1; done
   ```

   If `/health` never answers, `docker logs dossier-live` shows why.
3. **Research `runway.com` and save the response.** Request exactly `runway.com`. The build
   spends real Nimble credit:

   ```sh
   BASE=http://localhost:8000
   TOKEN=$(curl -s -X POST $BASE/auth/signup -H 'Content-Type: application/json' \
     -d '{"email": "live@example.com", "password": "live-dossier", "display_name": "Live"}' \
     | python3 -c 'import json, sys; print(json.load(sys.stdin)["token"])')
   curl -s -X POST $BASE/dossiers -H "Authorization: Bearer $TOKEN" \
     -H "Idempotency-Key: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
     -H 'Content-Type: application/json' -d '{"domain": "runway.com"}'
   while curl -s $BASE/dossiers/runway.com -H "Authorization: Bearer $TOKEN" \
     | grep -q '"state": *"building"'; do sleep 5; done
   curl -s $BASE/dossiers/runway.com -H "Authorization: Bearer $TOKEN" > dossier-runway.com.json
   ```
4. **Confirm it is `ready`, then stop the service.**

   ```sh
   python3 -c 'import json; d = json.load(open("dossier-runway.com.json")); print("state:", d["state"])
   w = max(map(len, d["fields"])); print("field".ljust(w), "| value"); print("-" * w, "+", "-" * 5)
   [print(f.ljust(w), "|", v["value"]) for f, v in d["fields"].items()]'
   ```

   A `failed` build leaves every field `unknown`. Read `docker logs dossier-live` before you
   remove the container. Then run `docker rm -f dossier-live`; if the build failed, fix
   the cause and repeat from step 2. Do not edit the file by hand.

   A `ready` build with most fields `unknown` usually means the service stopped waiting too
   soon. The live providers answer far more slowly than the sample ones: a Nimble search can
   take over ten seconds and a research run about a minute. `harness check` warns when
   more than half of the six fields are `unknown`.
5. **Commit it** and run `harness check`, which checks that the `runway.com` response
   is ready and has valid field shapes. The offline check cannot establish which
   stage completed or whether the data came from the live web.

During judging the organizers may run your highest counting stage once more against the live
web, researching `runway.com` and other real companies, as evidence for App. That run uses
the environment of step 2 with an organizer's Nimble key.

**If the folder you copy holds a `.git` directory, delete it.** A stage folder that is
its own repository is recorded as a link, not as files: everything is there in your
working directory and absent from a clone, so the folder builds for you and arrives
empty for a judge. `harness check` reports it.

Each folder is graded against **every suite up to its own number**: `stage-3/` runs
suites 1, 2 and 3, and it counts as a completed stage 3 only if it passes at least half of
each of the three suites. A suite's pass rate is the weighted average of its test files' pass
rates: each file weighs one, except some held-back files that weigh three. A
stage-3 service that broke stage 1 has not extended anything, and extending what already
works is the whole exercise.

**A folder that also passes the *next* stage's whole suite claims nothing.** If `stage-1/`
passes every stage 2 check, it is a stage 2 solution filed in the wrong folder, and it
earns no stage 1. The point of the four folders is to show requirements accumulating the
way they do on real work: build stage 1, then take stage 2's requirements and widen what
you built. Copying your final answer back into every folder defeats that and scores
nothing for the earlier ones.

`harness run --repo ... --stage N` runs this check for you and prints
`claimed stage: N on the shipped checks` or `claimed stage: none`.

Every folder below stage 4 is also checked against the next suite; only the practice `toy`
skips the `stage-2/` probe.

Submit only the folders you completed. A team that reached stage 2 submits `stage-1/`
and `stage-2/` and nothing else. An empty or half-finished `stage-3/` does not hurt the
folders below it — a folder that does not build claims nothing, exactly as an absent one
does, and either way the chain stops there. There is simply no reason to include it.
`stage-1/` is the one folder every entry must have: it is gate 3, and a `stage-1/` that
does not start is an unranked entry.

**The chain is what scores.** A folder counts only if every earlier folder counts too, so
a passing `stage-4/` above a failing `stage-2/` counts for nothing at stages 2, 3 or 4 — fix
the earlier folder before adding another. `harness run --repo <repo> --all` shows which
folders claim their stage in one run.

## Build and check each stage

Use one room and one result repository throughout. Give the band each spec in order,
asking it to copy the previous stage folder forward and extend it. Seats assign and
reply using each other's literal `@handles`. The coordinator must add every configured
seat to the room before its first handoff and retry a handoff if Jam reports that the
named seat is absent. A coordinator must paste the complete task
and spec into each delegated handoff; pointing at a room message id or asking a seat to
read the room is insufficient. Long handoffs can be split into numbered direct messages.
The implementer posts the full committed revision, and the reviewer independently runs
the checks against a handoff that also contains the complete requirements.

**Each stage is built from its own spec, starting from the previous stage's code.** No
seat reads or receives a stage's spec until the folder before it is final, and no folder
changes once a later spec has been opened. The four folders show requirements arriving
the way they do on real work; a stage 1 designed around stage 3 does not show that.
Judges see every point where a later spec reached the room before an earlier folder last
changed, and score Factory and Agent Teamwork lower for it.

Iterate on your factory as much as you like: try seats, mandates and whole bands, and
step in while you do. The run you submit is different. Once you have chosen the factory,
run it in a fresh room and a fresh result repository, and submit that room and those
mandates. Only that run is judged for Agent Teamwork.

In the submitted run, each stage is a **dark-factory run**. The task you dispatch is its only human input.
From that dispatch until the coordinator's final report, no seat may ask you for
clarification, approval, confirmation or another decision, or pause waiting for your
reply. Seats resolve choices from the supplied requirements and communicate within the
band. If they cannot proceed, the coordinator records the blocker and available evidence
as the stage outcome. Resolve event or specification questions before starting the stage.

You may dispatch each stage separately, or all four at once by naming the spec files
rather than pasting them; the lead then opens each spec only when its stage starts.
Either way, send nothing
between dispatches: a "looks good, continue" is steering, and dispatching the same stage
twice is a rerun.

### Example prompt for your lead seat

Once you have everything ready and you want to prepare for submission, you can give the lead the full stage sequence up front, by spec file.
The example below shows one way to do this. Replace `<WORKSPACE>` with the absolute path to the folder containing your `sf-buildathon-2026/`
kickoff checkout and `band-work/` workspace.
The kickoff checkout contains the specs, so the lead reads each one when its stage starts.
It must still include the complete task and spec in every delegated handoff.

```text
You are the lead seat for our factory. Build all four stages, coordinating the other
seats and keeping every stage in its own complete, buildable folder.

Workspace root: <WORKSPACE>
Working folder: <WORKSPACE>/sf-buildathon-2026
Track: dossier
Result repository: <WORKSPACE>/band-work/result

Build each stage from its own spec, starting from the previous stage's code. Do not
open a later stage's spec until the stage before it is complete, and do not change a stage
folder once the next spec is open. Keep every seat busy within the current stage.

For stage 1, read the full spec at:
<WORKSPACE>/sf-buildathon-2026/challenges/dossier/spec/stage-1.md
Implement it in:
<WORKSPACE>/band-work/result/stage-1/

When stage 1 is complete, copy it to stage-2 and extend that copy using spec/stage-2.md.
Continue with stage-3 and stage-4 using their full specs. Keep earlier stage folders
unchanged. Each stage folder must have its own Dockerfile, RUN.md and complete source.
Run the checks and resolve failures within the band. Record any blocker and its evidence
without asking the human for steering or approval.

Save wall-clock time: run independent work in parallel, such as reviewing while checks
run. Avoid repeating work another seat has already verified. Run one check at a time,
since parallel checks overload the machine and time out.
```

The real submission repository is the separate `band-work/result/` repo, not the kickoff
repo. Its stage folders are the outputs every seat shares and commits to.

To check a stage, run the harness. For example:

```sh
python -m harness run --track dossier --repo ../band-work/result --stage 3 \
  --out ../band-work/checks/s3-01
```

That builds `../band-work/result/stage-3/` and runs the checks for stages 1, 2 and 3
against it, then the stage 4 suite as the overshoot check. **That last one should fail** —
a `stage-3/` that passes suite 4 claims nothing — so ignore its line and read the last two:

```text
highest contiguous stage: 3
claimed stage: 3 on the shipped checks
report: ../band-work/checks/s3-01/report.json
NOTE: this run only includes a portion of the full tests that are applied before judging; this is meant to provide directional feedback, and ultimately you may not pass the stage with the full set of tests.
```

For `stage-N/`, you want `claimed stage: N`. `highest contiguous stage` is the last stage
whose every shipped check passed against this folder, so it can read lower than a stage
the folder still claims. `claimed stage: none` means a suite's average file pass rate is
below 50%, or that the folder also passes every check of the next stage.

The full judging suite can still reject a folder that claims its stage here. Before
moving on, check the requirements the shipped tests do not cover; see
[Do not write to the tests](#do-not-write-to-the-tests).

**Run your final check of each stage in isolated mode**, because that is how it will be
graded:

```sh
python -m harness run --track dossier --repo ../band-work/result --stage 3 \
  --mode isolated --out ../band-work/checks/s3-final
```

Swap `--stage 3` for `--all` to build every folder you have and see which ones claim their
stage.

Host mode is the default and is the right thing while you iterate, but it publishes a
port and does **not** block outbound network. Isolated mode runs on an internal network
with no outbound access, 2 vCPU and 3 GiB — a service that quietly depends on reaching
the internet at runtime passes in host mode and fails when judged.

Every check writes `report.json`, per-stage logs and count files into a **new**
directory. Existing output directories are refused: choose another name or omit `--out`
to get a unique directory under `runs/`. Preserve failures. In the submitted run the
band reads the failing log and fixes the implementation itself; handing it the log is for
while you develop the factory. Skips, deselection, missing browsers, empty suites
and startup errors cannot produce a passing stage.

Keep result repositories self-contained: no Git submodules or symlinks. Builds may fetch
dependencies. Each stage's service needs its own `Dockerfile`; Compose is optional and is
never read by the harness. All required services must work inside the single image. The
harness runs locally as a terminal command; your reviewer can run it. It is not a Band
Desktop seat and never posts messages.

## Do not write to the tests

Each stage ships part of its checks so your band can wire a service up and iterate: run a
stage, read the failing log, fix the implementation, run it again. Every stage ships
`test_sample.py`, which shows each surface once; selected stages also ship other files of
the graded suite, unchanged. The rest of each suite is held back. The files under
`challenges/<track>/test/stage_N/` and `kickoff-manifest.json` show what your package
includes. The share of each stage's checks that ships:

| Track | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|---|---:|---:|---:|---:|
| `dossier` | 57% | 6% | 4% | 8% |

During judging, the full set of tests are run to validate your solution.
Every one of them is written in the specification you were given, and a careful reading finds them.

**A green run on the shipped checks is not evidence of a stage.** When a stage looks done,
re-read its spec section and ask what the shipped checks never asked for — that question
is the work.

## Your mandates must be generic

**This is the rule teams most often break by accident, and it is disqualifying.** Read it
before you write a single mandate.

Your mandates describe **how your factory works**: what each seat owns, how it takes work,
how it hands work off, what makes it reject something, how it reports evidence. Nothing in
a mandate should tell a reader which challenge the factory is solving.

The task you paste into the room describes **what this track needs**. That is where the
spec goes. Pasting a whole spec into the room is expected and correct.

**A mandate may freely say** things like: "you implement one scoped work item at a time",
"you reject any change without a passing check", "post the committed revision in the room
when you are done", "read the specification the coordinator gives you and resolve
ambiguities within the band". None of that names a track.

The test to apply yourself: **could you hand these mandates to a team building something
completely different, and would they still make sense?** If not, they are not a factory —
they are a transcript of this problem. Factory carries 40% of the score and asks whether your
factory is generic and whether another team could stand it up from `FACTORY.md` and
`mandates/`.

## Agent Teamwork evidence

Agent Teamwork is read from your room log and your Git history, not from what you write
about it. Judges compare the two to see whether the seats shared the work, whether the
code came out of the room, and whether anyone outside the band steered it.

Good teamwork leaves a trail in both. The work is split between seats rather than carried
by one. Handoffs happen in the room and carry the whole task. Review is real: when a seat
rejects work, it says what failed, and the fix comes back through the room. Progress shows
up as commits made along the way, each traceable to the discussion that produced it.

Keep that trail intact. Push the history the seats made, without amending, rebasing or
squashing it, and leave the code under `stage-N/` to the band: anything you commit there
yourself is code the band did not write.

## Record the room

The room log is what shows the code came from your band. No harness command fetches it:
you download it from Band yourself and commit the file.

1. **Open the room in the Band console.** In Band Desktop, open the room you worked in,
   click the `⋮` menu at the top right of the room and choose **Open in Band**. The room
   opens in the Band console under **Sessions**. You can also sign in to the Band
   console directly and pick the room from **Sessions**.
2. **Download the full session.** In the console, click the room's `⋮` menu at the top
   right, then **Download → Download full session**. Do not use **Download filtered**,
   and it does not matter what the **Event type** and **Sender** filters are set to.
3. **Save the file, unchanged, as `room.json`** at the root of your result repository.
   Band names the file after the room, e.g. `Dossier.json` for a room called
   Dossier. Rename it, and do not edit its contents.

```sh
mv ~/Downloads/Dossier.json ../band-work/result/room.json
```

The file holds every message in the room, including the seats' tool calls and their
output, exactly as Band stored them. **Nothing redacts it.** Your repository is public,
so read it before you commit it: `harness check` scans `room.json` for credential
shapes like every other file, but it cannot recognise every private value. If it finds
one, rotate the credential and replace the value in `room.json` with `[REDACTED]`.

Download it at the end, after the work is done, so the log holds the whole
collaboration. Download it again whenever you want to refresh it, and overwrite
`room.json`.

If the band worked each stage in a room of its own, commit one download per stage
instead: `room-1.json` for the room that built `stage-1/`, `room-2.json` for `stage-2/`,
and so on, each downloaded the same way and left unchanged. Every stage folder you
commit then needs its room file, and `room.json` must not be there as well. The checks
count seats and `@handle` exchanges across the rooms together.

Delivery time is the time from the first to the last message a seat sent in the room, or
those times added up across the per-stage rooms. A pause inside a room counts, so submit
a room that holds the run you are submitting, not the weeks you spent building the factory.

## Check and submit

Run the offline check from the repository root before you push:

```sh
python -m harness check ../band-work/result --track dossier
```

It validates the folder layout, that `stage-1/` has a `Dockerfile` and a
`RUN.md`, that `room.json` is a whole-room download, that every seat in it has a
mandate file named after it, that every mandate names its harness and model, that two
seats really exchanged `@handle` messages in both directions, that no mandate names
track vocabulary, and that no file in the repository, `room.json` included, looks like
it holds a credential.
It builds nothing — gate 3 is `harness run --repo`.

For Dossier, it also checks that `dossier-runway.com.json` is a `GET /dossiers/runway.com`
ready response with valid field shapes: six base fields, optionally `executives`, then
`investors`. It cannot establish the highest completed stage or prove live-web provenance;
verify those against your run and the stage reports before submitting.

Commit the result, push to a public GitHub repository, and give its URL, presentation and video to the event lead through the submission channel announced for this event. The organizer records the judged commit at the deadline.

Write `README.md` and `FACTORY.md` yourself. `FACTORY.md` is what judges read to decide
whether another team could stand your factory up: seat ownership and setup, your design
choices and the reasons for them, what you tried that failed, measured costs and time, and
how your factory catches a bad result. Agent Teamwork is not written — it is read out of
your room log and your commit history, so the way to show it is to actually work in the
room and leave the band to run.

## Practice on the toy example

Everything above is the real track. The toy is where you rehearse it first, on a problem
small enough to read in a minute, before you hand your band a spec that counts.

`toy` is an unscored four-stage exercise. It builds one shared counter: the API, then a
page with an increment button, then 20 simultaneous increments with none lost, then a
request that chooses how much to add.

The toy has the same delivery loop as `dossier`: one service folder per stage, cumulative checks and independent review.

Its specs are `challenges/toy/spec/stage-1.md` through `challenges/toy/spec/stage-4.md`.

The supplied mandates are **minimal practice templates** for assignments, handoffs and
basic review, not a complete factory design. Adapt your workflow for the graded challenges;
short mandates are allowed, but a successful toy run does not establish their effectiveness
on the real tracks.

Prepare a separate practice repository the same way:

```sh
mkdir -p ../band-work/toy-result/stage-1 ../band-work/toy-result/mandates
cp scaffold/* ../band-work/toy-result/stage-1/
cp challenges/toy/mandates/*.md ../band-work/toy-result/mandates/
git -C ../band-work/toy-result init -b main
(cd ../band-work/toy-result && pwd)
```

`scaffold/` is a starting service, not a solution. It answers `/health` and
`/_test/reset` and hashes passwords, and that is all — your band writes the rest. Using
it is optional; any language is fine.

Paste `stage-1.md` into one Band Desktop room with the absolute path that prints:

> Build this shared-counter service one stage at a time. The result repository is
> `/absolute/path/to/band-work/toy-result`. Stage 1 goes in `stage-1/`; when it passes,
> copy that folder to `stage-2/` and extend the copy, and the same again for `stage-3/`
> and `stage-4/`. Produce source files, a Dockerfile and RUN.md in each, and commit
> nowhere else. Have the reviewer check each stage, and after each one post the full
> committed revision in the room.

Use the same room and repository for all four stages so the band extends the service it
already built. Paste one stage's spec at a time, or give the lead all four as in
[Example prompt for your lead seat](#example-prompt-for-your-lead-seat), and stop wherever
you like: the point is to run the loop, not to finish the toy.

Check each stage as it lands:

```sh
python -m harness run --track toy --repo ../band-work/toy-result --stage 1 \
  --out ../band-work/checks/toy-s1
python -m harness run --track toy --repo ../band-work/toy-result --stage 2 \
  --out ../band-work/checks/toy-s2
python -m harness run --track toy --repo ../band-work/toy-result --stage 3 \
  --out ../band-work/checks/toy-s3
python -m harness run --track toy --repo ../band-work/toy-result --stage 4 \
  --out ../band-work/checks/toy-s4
```

`--stage N` runs stage N's suite **and every earlier stage's** against that folder, so a
stage-4 check prints four `pass` lines, not one. **`--stage 1` and `--stage 3` also print
one `fail` line, and that is intended:** it is the next stage's suite, run to check the
folder did not overshoot. A clean stage 1 run:

```text
  stage 1: pass
  stage 2: fail
highest contiguous stage: 1
claimed stage: 1 (100% of its own suite)
```

| Stage | Its own suite | A passing `--stage N` run prints |
|---|---|---|
| 1 | 8 API checks | `stage 1: pass`, `stage 2: fail`, then `highest contiguous stage: 1` |
| 2 | 4 browser checks | stages 1 and 2 pass, `highest contiguous stage: 2` |
| 3 | 2 concurrency checks | stages 1 to 3 pass, `stage 4: fail`, `highest contiguous stage: 3` |
| 4 | 10 checks, 2 of them concurrent | stages 1 to 4 pass, `highest contiguous stage: 4` |

Whatever the other lines say, the last one, `claimed stage: N`, tells you the folder is
right. `--all` prints one line per folder and does not add the chain up for you: count from
`stage-1/` and stop at the first folder that does not claim its stage.

Check it before the band has written anything and stage 1 fails, which is expected: the
scaffold answers health and reset but has no counter, so **2 of the 8 stage-1 checks pass
and 6 fail**. The terminal prints only `stage 1: fail` — the counts are in the
`stage-1.log` it names on that line. Once the band has implemented the counter you will
see `stage 1: pass` instead, and that is the exercise. Give the band a failing stage's
log and ask it to fix the implementation; if Docker cannot build or the service never
starts, give it the terminal error, because the tests cannot run until that is fixed.
Stage 4 is where a band that special-cased its way through stage 3 finds out: the lock
it wrote has to hold for an amount it did not know about.

Confirm the *reviewer* ran these checks, not the implementer, and that the room holds a
message from a seat naming the committed revision. What to look for is in
[Build and check each stage](#build-and-check-each-stage); the toy is the cheap place to
find out whether your seats actually produce it.

**Finish the loop on the toy, too.** Passing the checks is half of it; the other half is
the submission, and that is where entries are lost. On your toy repository, follow
[Record the room](#record-the-room) into `../band-work/toy-result/room.json`, then run
the offline check:

```sh
python -m harness check ../band-work/toy-result --track toy
```

It lists what a submission still needs — `README.md`, `FACTORY.md`, `mandates/` with
their `Harness:` and `Model:` lines filled in, `room.json` — and it is the only check that proves gates 1 and 2 without Docker, so it takes a
minute. Fix those on the toy now and both gates are rehearsed before the real repository
matters. Gate 2 clears only once two of your seats have exchanged `@handle` messages in
the room, with a reply in each direction, which is what the toy is for.

One difference from the real tracks: the toy ships its **whole** suite, because its job
is to show you the loop. Your track ships part of each stage's checks and the rest stay
with the judges — see [Do not write to the tests](#do-not-write-to-the-tests).
Do not read the toy's green run as what a green run on your track proves.

The first isolated run installs the runner's dependencies and browser in Docker and takes longer;
time it now rather than on the last day.

## Before you submit

Work through this against a fresh clone, not the directory you worked in.

1. Clone your pushed repository somewhere new and run `harness check` there. A file you
   forgot to commit, and a stage folder that is its own git repository, are both
   invisible from your working directory and both arrive empty for a judge. This step is
   the only one that shows them.
2. Run `python -m harness run --track dossier --repo <clone> --all --mode isolated` once. It shows which folders
   claim their stage on the shipped checks; the organizers' full run decides which count.
3. Follow each stage's `RUN.md` by hand in a clean environment, then use the UI. No
   offline check covers this. For `stage-1/` it is gate 3; for every other folder it is
   what lets the folder claim its stage, and a service that does not start counts for
   nothing at that stage or any above it.
4. Read `room.json` and confirm the reciprocal `@handle` exchange between two of
   your seats is really there, and that no history was rewritten
   ([Agent Teamwork evidence](#agent-teamwork-evidence)).
5. Confirm `README.md` and `FACTORY.md` are written, not placeholders.
   Open `dossier-runway.com.json` and confirm its `state` is `ready` and that it came
   from your highest completed stage, built against the live web.
6. Re-read every mandate and ask whether a team building something else could use it.
   Anything naming your track's endpoints, fields, error codes or test ids has to go.
7. Skim the repository for anything private that automatic redaction would not
   recognise. If you find a credential, rotate it — deleting the line does not unpublish
   what was already pushed.
8. Submit the repository URL, the presentation and the video, then keep the receipt.

## Optional setup

Nothing here is required, scored or checked.

### Optional: run a seat in a Docker Sandbox

Band Desktop can start a seat's runtime inside a [Docker Sandbox](https://www.docker.com/products/docker-sandboxes/) —
a microVM with its own filesystem, network boundary and Docker daemon — so that seat builds
and commits without holding those permissions on your machine. That makes it safer to
give a seat the broad permissions an unattended run needs: a wrong command, or a harmful
instruction hidden in something the seat reads, reaches only its working directory and
the network its policy allows, not your home directory, credentials or other
repositories. It is optional, it changes nothing you submit, and no gate depends on it.

You also need Band Desktop 0.4.10 or newer, Docker Sandboxes 0.42 or newer, and a
supported host — macOS 14+ on Apple silicon, Windows 11, or Ubuntu 24.04+ with KVM.

**Install `sbx`.** It is its own download — Docker Desktop neither provides it nor is
required for it:

```sh
# macOS 14+ on Apple silicon
brew trust docker/tap && brew install docker/tap/sbx

# Ubuntu 24.04+ with KVM — the repository, then the package
curl -fsSL https://get.docker.com | sudo REPO_ONLY=1 sh
sudo apt install docker-sbx
```

On Windows 11, enable the hypervisor first, then install from an elevated PowerShell:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -All
winget install -h Docker.sbx
```

Docker's own guide wins if it disagrees with the above:
<https://docs.docker.com/ai/sandboxes/install/>. Then sign in and start the daemon:

```sh
sbx version                      # 0.42 or newer
sbx login
sbx daemon start --detach
sbx policy ls                    # if it reports no policy yet:
sbx policy init balanced
```

Band Desktop starts sandboxes without a terminal, so it cannot answer the network-policy
prompt `sbx` shows before a first sandbox. Do not reset a policy that already exists.

**Give the seat a credential.** A sandboxed seat cannot use your host Claude login.

| Paying with | Do this |
|---|---|
| An Anthropic **API key** | `sbx secret set anthropic` and paste it, or `echo "$ANTHROPIC_API_KEY" \| sbx secret set anthropic` |
| A Claude **subscription** | From an empty scratch directory, `sbx run --name sbx-login claude`, then `/login` inside it; exit, then `sbx rm sbx-login`. `sbx secret set` cannot store a subscription. `sbx secret ls` should now show `anthropic` as `(oauth configured)` |

**On macOS, let Band Desktop see `sbx`.** Homebrew installs it to `/opt/homebrew/bin`,
which a GUI app does not inherit, so the runtime check reports `sbx` missing however
happily your terminal runs it. Set the PATH, then reboot:

```sh
sudo launchctl config user path "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
```

`launchctl config` takes effect only after a reboot (`man launchctl`). Quitting and
reopening Band Desktop is not enough, and neither is restarting its background daemon.

**Turn it on.** **Settings → Experiments → Docker Sandboxes**, then **Settings → Runtime
→ Re-check**. Only a seat Band Desktop runs itself can be sandboxed: create it with
**New local agent** as a headless Claude Code, Codex, GitHub Copilot or Cursor seat.
OpenCode seats, and any session you started yourself, stay on the host. The credential
and setup steps in this section are for Claude Code; for the other harnesses, follow
Band Desktop's advanced reference.

Choose the sandbox when you create the seat:
**Docker Sandbox** on, **Direct host workspace** mode, and **Working directory** set to
the absolute path of `../band-work/result` — the same path you give the band, so the
seat's commits land in your repository rather than a copy you cannot see. For the
credential, pick **Docker-managed Anthropic credential** — it covers both the key and
the subscription. Run **Test runtime** before
you give the seat work; if it cannot authenticate, give it an API key or run it on the
host.

Nothing else moves: the room, the room download and the submission layout are
unchanged, and `python -m harness run` still runs on your machine rather than inside a
sandbox.

### Optional: shared memory with Cognee

Cognee's MCP server can give your seats one memory they all read and write, across stages.
Nothing requires or scores it; if your factory uses it, say how in `FACTORY.md`.

Run one server over HTTP, so every seat shares it. Keep its model key in a file outside the
result repository:

```sh
# ~/.cognee.env: LLM_API_KEY=...  and  COGNEE_MCP_AGENT_SCOPED=false
docker run --rm -d --name cognee -e TRANSPORT_MODE=http --env-file ~/.cognee.env \
  -p 8765:8000 cognee/cognee-mcp:main
```

`COGNEE_MCP_AGENT_SCOPED=false` puts every seat in one dataset; without it each harness
writes its own. Port 8765 keeps it clear of the services you run on 8000 and 8080. Then add
it to each seat at user scope (`-s project` would write `.mcp.json` into your repository):

```sh
claude mcp add --transport http cognee http://localhost:8765/mcp   # Claude Code seats
codex mcp add cognee --url http://localhost:8765/mcp               # Codex seats
```

It helps most with what the repository does not already hold: rulings on unclear spec
points, review findings and how they were fixed, and why a design was chosen. Have seats
`remember` those as they happen and `recall` them before each stage. Handoffs still go
through the room, which is what judges read. Cognee is a tool for the factory, not part of
the service: a Dossier service calls only the provider base URLs it is given.

## Getting help

Ask Band Desktop and harness questions in the BAND Discord: <https://discord.com/invite/5YkNXmYfjk>. Submission questions go to the event lead through the channel announced before registration.

If you find a genuine ambiguity in a published spec, ask. Clarifications are answered
**publicly to every team**, because everyone builds the same specification.
