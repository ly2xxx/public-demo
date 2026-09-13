#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Delivery metrics from git history, split at the commit that introduced the gates.

The claim this script exists to support is narrow and checkable: after the gated
workflow landed, changes got smaller and tests started arriving with them. Both
halves come from the same source (``git log --numstat``), so the comparison is
apples to apples, and the split point is *derived* rather than chosen -- see
``detect_cutover``.

    uv run metrics/delivery_metrics.py --repo . --repo ../langgraph_ollama
    uv run metrics/delivery_metrics.py --repo . --json metrics.json --markdown METRICS.md

What it deliberately does NOT measure: PR cycle time, review latency, or anything
else needing the forge API. Those are the numbers a team would care about; this is
a single-operator history and the report says so out loud rather than implying
otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path

# ---------------------------------------------------------------------------
# What counts as signal
# ---------------------------------------------------------------------------

# Paths whose line counts say nothing about how a human works: lockfiles are
# machine-written, binaries have no meaningful line count, and notebooks store
# their own output, so one re-run rewrites thousands of lines. Left in, any of
# these swamps the distribution -- the raw p90 across these repos is ~600 lines
# and the raw max ~61k, and the 61k is a lockfile.
EXCLUDE_GLOBS = (
    "*.lock", "uv.lock", "package-lock.json", "poetry.lock", "yarn.lock",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg", "*.webp", "*.jfif", "*.ico",
    "*.pdf", "*.zip", "*.whl", "*.excalidraw",
    "*.ipynb",
    "*.csv", "*.tsv", "*.json.gz",
    "*/node_modules/*", "*/.venv/*", "*/site-packages/*",
    "*/all-MiniLM-L6-v2/*", "*/datasets/*", "*/images/*", "*/image/*", "*/assets/*",
    "requirements.txt",  # exported from the lock, not hand-edited
)

TEST_GLOBS = (
    "test_*.py", "*_test.py", "*/tests/*", "*/test/*",
    "*.feature", "*/features/*", "conftest.py", "*/fakes/*",
)

# Files that only exist because the workflow demands them: a frozen design, a
# phase log, a quality report, a BDD scenario, an agent instruction file. The
# first commit to add any of them is the workflow arriving in that repo.
MARKER_GLOBS = (
    "DESIGN.md", "PHASED.md", "PHASED_PLAN.md", "QUALITY_REPORT.md",
    "*.feature",
    "*/coding_agent/*",
    ".claude/*", "*/.claude/*", ".agents/*", "*/.agents/*",
    "CLAUDE.md", "AGENTS.md",
    "*/deterministic-coding/*",
    "ai-coding-prompt*.txt",
)

# A commit that exists to correct a previous one. Crude, and the report labels it
# a proxy: it counts what the author *called* rework, not what was.
REWORK_RE = re.compile(
    r"^\s*(revert|fix(up)?|hotfix|patch|oops|typo|whoops|correct|amend|"
    r"re-?fix|bug ?fix)\b",
    re.IGNORECASE,
)

SEP_REC, SEP_FLD = "\x01", "\x02"


def matches(path: str, globs: tuple[str, ...]) -> bool:
    p = path.replace("\\", "/")
    return any(fnmatch(p, g) or fnmatch("/" + p, g) for g in globs)


# ---------------------------------------------------------------------------
# Reading history
# ---------------------------------------------------------------------------


@dataclass
class Commit:
    sha: str
    when: datetime
    subject: str
    code_lines: int = 0
    test_lines: int = 0
    doc_lines: int = 0
    files: set[str] = field(default_factory=set)

    @property
    def total_lines(self) -> int:
        return self.code_lines + self.test_lines + self.doc_lines

    @property
    def touches_tests(self) -> bool:
        return self.test_lines > 0

    @property
    def is_rework(self) -> bool:
        return bool(REWORK_RE.match(self.subject))


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {out.stderr.strip()}")
    return out.stdout


def read_commits(repo: Path) -> list[Commit]:
    """Every non-merge commit with its per-file line counts.

    Merges are excluded: their numstat is relative to one parent and double-counts
    work already attributed to the commits being merged.
    """
    raw = git(
        repo, "log", "--no-merges", "--numstat", "--date=unix",
        f"--format={SEP_REC}%H{SEP_FLD}%at{SEP_FLD}%s",
    )
    commits: list[Commit] = []
    for record in raw.split(SEP_REC)[1:]:
        header, _, body = record.partition("\n")
        sha, at, subject = (header.split(SEP_FLD) + ["", ""])[:3]
        commit = Commit(
            sha=sha,
            when=datetime.fromtimestamp(int(at), tz=timezone.utc),
            subject=subject.strip(),
        )
        for line in body.splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            added, removed, path = parts
            if added == "-" or removed == "-":  # binary
                continue
            if matches(path, EXCLUDE_GLOBS):
                continue
            changed = int(added) + int(removed)
            commit.files.add(path)
            if matches(path, TEST_GLOBS):
                commit.test_lines += changed
            elif path.endswith((".md", ".rst", ".txt")):
                commit.doc_lines += changed
            else:
                commit.code_lines += changed
        if commit.files:
            commits.append(commit)
    commits.sort(key=lambda c: c.when)
    return commits


def detect_cutover(repo: Path) -> tuple[datetime | None, str]:
    """When the gated workflow arrived, as the earliest commit adding a marker file.

    Derived, not chosen -- so the split can't be nudged to flatter the numbers.
    Returns the timestamp and the path that triggered it, for the report to cite.
    """
    raw = git(
        repo, "log", "--no-merges", "--diff-filter=A", "--name-only",
        "--date=unix", f"--format={SEP_REC}%H{SEP_FLD}%at",
    )
    earliest: tuple[datetime, str] | None = None
    for record in raw.split(SEP_REC)[1:]:
        header, _, body = record.partition("\n")
        fields = header.split(SEP_FLD)
        if len(fields) < 2:
            continue
        when = datetime.fromtimestamp(int(fields[1]), tz=timezone.utc)
        for path in body.splitlines():
            path = path.strip()
            # A screenshot dropped in a workflow directory is not the workflow
            # arriving; the same exclusions that keep binaries out of the line
            # counts keep them from setting the split point.
            if matches(path, EXCLUDE_GLOBS):
                continue
            if path and matches(path, MARKER_GLOBS):
                if earliest is None or when < earliest[0]:
                    earliest = (when, path)
    return (earliest[0], earliest[1]) if earliest else (None, "")


# ---------------------------------------------------------------------------
# Summarising
# ---------------------------------------------------------------------------


def pct(xs: list[int], q: float) -> int:
    """Nearest-rank percentile. Explicit so the number in the report is one
    anybody can reproduce with sort | sed -n, no interpolation convention to
    argue about."""
    if not xs:
        return 0
    ordered = sorted(xs)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[idx]


MIN_REPORTABLE = 10


def summarise(commits: list[Commit]) -> dict:
    if not commits:
        return {"commits": 0}
    # Code-only sizes are the honest basis for "did changes get smaller": the
    # gated workflow *mandates* a long DESIGN.md and an append-only PHASED.md,
    # so counting doc lines makes the workflow look like it inflated changes
    # when what it did was write down the plan. Both are reported.
    sizes = [c.total_lines for c in commits]
    code_sizes = [c.code_lines + c.test_lines for c in commits if c.code_lines + c.test_lines]
    files = [len(c.files) for c in commits]
    with_tests = [c for c in commits if c.touches_tests]
    code = sum(c.code_lines for c in commits)
    test = sum(c.test_lines for c in commits)
    days = {c.when.date() for c in commits}
    return {
        "commits": len(commits),
        "reportable": len(commits) >= MIN_REPORTABLE,
        "first": commits[0].when.date().isoformat(),
        "last": commits[-1].when.date().isoformat(),
        "active_days": len(days),
        "commits_per_active_day": round(len(commits) / len(days), 2),
        "median_lines": int(statistics.median(sizes)),
        "mean_lines": int(statistics.fmean(sizes)),
        "p90_lines": pct(sizes, 0.90),
        "max_lines": max(sizes),
        "code_commits": len(code_sizes),
        "median_code_lines": int(statistics.median(code_sizes)) if code_sizes else None,
        "p90_code_lines": pct(code_sizes, 0.90) if code_sizes else None,
        "median_files": int(statistics.median(files)),
        "pct_commits_with_tests": round(100 * len(with_tests) / len(commits), 1),
        "test_to_code_ratio": round(test / code, 2) if code else None,
        "pct_rework_commits": round(
            100 * sum(c.is_rework for c in commits) / len(commits), 1
        ),
        "pct_commits_over_400_lines": round(
            100 * sum(s > 400 for s in sizes) / len(commits), 1
        ),
        "size_histogram": histogram(sizes),
        "code_size_histogram": histogram(code_sizes),
    }


HIST_BUCKETS = ((0, 50), (50, 150), (150, 400), (400, 1000), (1000, None))


def histogram(sizes: list[int]) -> list[dict]:
    out = []
    for low, high in HIST_BUCKETS:
        n = sum(1 for s in sizes if s > low and (high is None or s <= high))
        out.append({
            "label": f"{low+1}–{high}" if high else f"{low+1}+",
            "low": low + 1,
            "high": high,
            "commits": n,
            "pct": round(100 * n / len(sizes), 1) if sizes else 0.0,
        })
    return out


def analyse(repo: Path, cutover_override: datetime | None) -> dict:
    commits = read_commits(repo)
    detected, marker = detect_cutover(repo)
    cutover = cutover_override or detected
    before = [c for c in commits if cutover and c.when < cutover]
    after = [c for c in commits if cutover and c.when >= cutover]
    return {
        "repo": repo.name,
        "cutover": cutover.isoformat() if cutover else None,
        "cutover_source": "override" if cutover_override else (marker or "none found"),
        "total_commits": len(commits),
        "before": summarise(before),
        "after": summarise(after if cutover else commits),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

ROWS = (
    ("median_code_lines", "Median code+test lines / commit", "lower"),
    ("p90_code_lines", "p90 code+test lines / commit", "lower"),
    ("median_lines", "Median lines / commit (incl. docs)", "lower"),
    ("median_files", "Median files touched / commit", "lower"),
    ("pct_commits_with_tests", "Commits shipping tests (%)", "higher"),
    ("test_to_code_ratio", "Test lines per code line", "higher"),
    ("pct_rework_commits", "Rework-labelled commits (%)", "lower"),
)


def fmt(v) -> str:
    return "—" if v is None else (f"{v:g}" if isinstance(v, float) else str(v))


def arrow(before, after, good: str) -> str:
    if before is None or after is None or before == after:
        return ""
    improved = (after < before) if good == "lower" else (after > before)
    return " ✓" if improved else " ✗"


def markdown(results: list[dict], combined: dict) -> str:
    lines = [
        "# Delivery metrics",
        "",
        "Generated by `metrics/delivery_metrics.py` from git history. Every figure is",
        "reproducible from the same command; nothing here is hand-entered.",
        "",
        "**Split point.** Each repo is divided at its own earliest commit adding a",
        "gated-workflow artefact (`DESIGN.md`, `PHASED.md`, a `.feature` file, an agent",
        "instruction file). The date is derived from history, not chosen.",
        "",
        "**What this is not.** Single-operator history on personal repositories. No PR",
        "cycle time, no review latency, no lead time to production — those need forge",
        "data and a team. Generated files, binaries, notebooks and lockfiles are excluded",
        "(see `EXCLUDE_GLOBS`); with them in, one lockfile commit is 61k lines and the",
        "distribution means nothing.",
        "",
        "## All repositories combined",
        "",
    ]
    lines += table(combined["before"], combined["after"])
    for r in results:
        lines += [
            "",
            f"## {r['repo']}",
            "",
            f"- Split at **{(r['cutover'] or 'n/a')[:10]}** "
            f"(first marker: `{r['cutover_source']}`)",
            f"- {r['total_commits']} non-merge commits with countable changes",
            "",
        ]
        lines += table(r["before"], r["after"])
    lines += ["", "---", "", f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC._"]
    return "\n".join(lines) + "\n"


def table(before: dict, after: dict) -> list[str]:
    if not before.get("commits"):
        return ["_No commits before the split point — the workflow was there from the start._"]
    rows = [
        "| Metric | Before | After | |",
        "| --- | --: | --: | :-- |",
    ]
    for key, label, good in ROWS:
        b, a = before.get(key), after.get(key)
        rows.append(f"| {label} | {fmt(b)} | {fmt(a)} |{arrow(b, a, good)} |")
    rows += [
        "",
        f"Before: {before['commits']} commits, {before['first']} → {before['last']}. "
        f"After: {after['commits']} commits, {after['first']} → {after['last']}.",
    ]
    for side, label in ((before, "before"), (after, "after")):
        if not side.get("reportable"):
            rows.append(
                f"\n> ⚠ Only {side['commits']} commits {label} the split "
                f"(< {MIN_REPORTABLE}). Treat this side as anecdote, not measurement."
            )
    return rows


def combine(repos: list[Path], overrides: dict[str, datetime]) -> tuple[list[dict], dict]:
    results, all_before, all_after = [], [], []
    for repo in repos:
        detected, marker = detect_cutover(repo)
        cutover = overrides.get(repo.name) or detected
        commits = read_commits(repo)
        all_before += [c for c in commits if cutover and c.when < cutover]
        all_after += [c for c in commits if cutover and c.when >= cutover]
        results.append(analyse(repo, overrides.get(repo.name)))
    return results, {"before": summarise(all_before), "after": summarise(all_after)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", action="append", required=True, type=Path,
                    help="repository path; repeat for several")
    ap.add_argument("--cutover", action="append", default=[], metavar="NAME=YYYY-MM-DD",
                    help="override the derived split point for one repo")
    ap.add_argument("--json", type=Path, help="write raw metrics here")
    ap.add_argument("--markdown", type=Path, help="write the report here")
    args = ap.parse_args()

    overrides: dict[str, datetime] = {}
    for spec in args.cutover:
        name, _, date = spec.partition("=")
        overrides[name] = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)

    repos = [p.resolve() for p in args.repo]
    for repo in repos:
        if not (repo / ".git").exists():
            print(f"not a git repository: {repo}", file=sys.stderr)
            return 1

    results, combined = combine(repos, overrides)
    report = markdown(results, combined)

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "combined": combined,
        "repos": results,
    }
    if args.json:
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
