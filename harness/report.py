"""Versioned conformance reports. A report records what a run did, and is never
evidence on its own: judges rerun every submission with their own harness."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import subprocess
from typing import Mapping

from harness.challenges import available
from harness.provenance import suite_digest

STAGES = ("1", "2", "3", "4")
PASS, FAIL, SKIP, ERROR = "pass", "fail", "skip", "error"
STATUSES = (PASS, FAIL, SKIP, ERROR)


def highest_contiguous(stages: Mapping[str, str]) -> int:
    """Highest N where stages 1..N all passed. 0 if stage 1 did not pass.

    Contiguous is deliberate: passing stage 3 while stage 2 fails scores stage 1.
    """
    reached = 0
    for stage in STAGES:
        if stages.get(stage) != PASS:
            break
        reached = int(stage)
    return reached


# A stage folder counts when its own suite, and every earlier suite it still runs,
# passes at least this share of its checks.
PASS_BAR = 0.5


# A held `test_trap_*.py` file holds only checks that fail on a stage's trap, and weighs
# this many ordinary test files.
TRAP_WEIGHT = 3


def pass_rate(counts: Mapping | None) -> float:
    """Weighted mean of each test file's pass rate. A file is one requirement area, so a
    one-check file weighs as much as a fifty-check error table; a trap file weighs
    TRAP_WEIGHT files."""
    weighted = [(TRAP_WEIGHT if pathlib.PurePath(name).name.startswith("test_trap_") else 1,
                 f["passed"] / f["total"])
                for name, f in ((counts or {}).get("files") or {}).items() if f.get("total")]
    weight = sum(w for w, _ in weighted)
    return sum(w * rate for w, rate in weighted) / weight if weight else 0.0


def claims(checks: Mapping, stage: str) -> bool:
    """A folder claims its stage when its own suite and every earlier one are each at
    PASS_BAR or better."""
    return all(pass_rate(checks.get(s)) >= PASS_BAR for s in STAGES if s <= stage)


def build_summary(track: str, folders: Mapping[str, Mapping], **metadata) -> dict:
    """What one `--all` run decided, across every stage folder it built."""
    ordered = {s: dict(folders[s]) for s in STAGES if s in folders}
    return {
        "track": track,
        "folders": ordered,
        **metadata,
    }


def git_revision(repo: pathlib.Path | str) -> str:
    """Full commit hash of `repo`, or "" when it is not a git checkout."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def now() -> str:
    """UTC, RFC 3339, including microseconds. Comparable against the room transcript."""
    return dt.datetime.now(dt.timezone.utc).isoformat()


def build(track: str, stages: Mapping[str, str], revision: str = "",
          started_at: str = "", finished_at: str = "", **metadata) -> dict:
    """A report for one run. Rejects unknown stages and statuses."""
    for stage, status in stages.items():
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}")
        if status not in STATUSES:
            raise ValueError(f"unknown status {status!r} for stage {stage}")
    ordered = {s: stages[s] for s in STAGES if s in stages}
    return {
        "revision": revision,
        "track": track,
        "stages": ordered,
        "highest_contiguous": highest_contiguous(ordered),
        "started_at": started_at,
        "finished_at": finished_at,
        **metadata,
    }


def write(path: pathlib.Path | str, report: Mapping) -> pathlib.Path:
    """Write `report` as indented JSON, creating parent directories."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def complete_counts(counts: Mapping) -> bool:
    """No skipped, deselected, xfailed, errored, or unexecuted checks count as green."""
    if not isinstance(counts, dict):
        return False
    # Exact type on purpose: a bool is an int subclass and is not a count.
    if any(type(v) is not int or v < 0  # pylint: disable=unidiomatic-typecheck
           for k, v in counts.items() if k not in ("files", "economy")):
        return False
    return (counts.get("collected", 0) > 0
            and counts.get("passed", 0) == counts["collected"]
            and all(counts.get(k, 0) == 0 for k in
                    ("failed", "errors", "skipped", "deselected", "xfailed")))


def validate(report: Mapping, track: str | None = None) -> list[str]:  # pylint: disable=too-many-branches
    """Reject inconsistent reports before using their claimed highest stage."""
    issues = []
    if not isinstance(report, dict):
        return ["report must be an object"]
    stages = report.get("stages")
    if not isinstance(stages, dict) or not stages or any(
            s not in STAGES or v not in STATUSES for s, v in stages.items()):
        return ["invalid stage results"]
    if report.get("track") not in available():
        issues.append("invalid track")
    if track and report.get("track") != track:
        issues.append("report track does not match the track asked for")
    if (type(report.get("highest_contiguous")) is not int  # pylint: disable=unidiomatic-typecheck
            or report["highest_contiguous"] != highest_contiguous(stages)):
        issues.append("highest_contiguous disagrees with stage results")
    if report.get("schema_version") != 2:
        issues.append("report schema is not version 2; rerun with the event harness")
    try:
        start, end = (dt.datetime.fromisoformat(report[k])
                      for k in ("started_at", "finished_at"))
        if start.tzinfo is None or end.tzinfo is None or end < start:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        issues.append("invalid run timestamps")
    if (not isinstance(report.get("run_id"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", report["run_id"])):
        issues.append("invalid run id")
    if not isinstance(report.get("checks"), dict):
        return issues + ["checks must be an object"]
    if report.get("state") not in ("running", "completed", "interrupted", "error"):
        issues.append("invalid run state")
    # A finished, unfiltered run is held to what it reports: a stage marked pass must
    # have executed every check, against the suite the event shipped.
    if report.get("state") == "completed" and not report.get("pytest_args"):
        for stage, status in stages.items():
            if status == PASS and not complete_counts(report.get("checks", {}).get(stage, {})):
                issues.append(f"stage {stage} did not execute every check")
        if (report.get("track") not in available()
                or report.get("suite_digest") != suite_digest(report["track"], stages)):
            issues.append("conformance sources differ; use the event release and rerun")
    return issues
