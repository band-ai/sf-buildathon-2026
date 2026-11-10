# BAND Dark Factory Buildathon: San Francisco

This is the kickoff package for BAND Dark Factory Buildathon: San Francisco. You build a software factory in [Band Desktop](https://docs.band.ai/band-desktop) from [BAND](https://www.band.ai/) — at least three coding-agent seats that plan the work, implement it, hand off evidence and check each other's results — and have it build the service specified here, one stage at a time. All stages are released at kickoff.

**Read the [participant guide](docs/participant-guide.md) before anything else.** It is the authoritative source for the rules, gates, rubric, setup and submission steps. This README only tells you where things are.

## What's in this repository

| Path | What it is |
|---|---|
| [`docs/participant-guide.md`](docs/participant-guide.md) | Rules, rubric and step-by-step instructions |
| [`challenges/dossier/`](challenges/dossier/) | Dossier: a company-research service that builds a profile of six fields from the web, through Nimble, called through WebRouter. `spec/stage-1.md`…`stage-4.md` and part of each stage's tests |
| [`challenges/toy/`](challenges/toy/) | Unscored practice track with the same shape as the real ones, plus sample mandates for three seats |
| [`scaffold/`](scaffold/) | Minimal Python service, used only by the toy walkthrough |
| [`harness/`](harness/) | The `python -m harness` CLI that builds your stage folders and runs the checks |
| `kickoff-manifest.json` | SHA-256 of every file in this release |

The result you submit is a **separate** repository your band builds; nothing you submit goes into this one.

## About BAND

[BAND](https://www.band.ai/) is the company behind Band Desktop, where the seats of your factory work together in one room.

- [Install Band Desktop](https://docs.band.ai/band-desktop)
- [BAND documentation](https://docs.band.ai/)
- [Create a BAND account](https://app.band.ai/)
- [BAND hacker guide](https://www.band.ai/hacker-guide)
- [BAND Discord](https://discord.com/invite/5YkNXmYfjk) for any questions about Band

## License

[Apache 2.0](LICENSE).
