#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The deterministic quality gate. Runs the same way in CI and inside an agent run.

Two properties matter more than what it checks:

1. **It calls no model.** Not "shouldn't" — cannot: this module imports nothing
   that can open a socket to a provider, and ``tests/test_gate.py`` asserts that
   statically against the import graph. "The tests passed" must never be
   something a model decided.

2. **It is the same binary in both places.** CI runs this file; the
   coding-engineer's ``self_check`` node runs this file. A gate that differs
   between the two is a gate that lets work through on one path and not the
   other, and the agent learns to prefer the lenient one.

    python gate/run_gate.py --target /work/repo --report QUALITY_REPORT.md

Exit codes: 0 clean, 1 a check failed, 2 the gate could not run (missing tool,
bad target) -- distinguished because the second is an infrastructure problem and
should not read as a code failure to whatever is consuming the result.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

EXIT_CLEAN, EXIT_FAILED, EXIT_UNRUNNABLE = 0, 1, 2

# pytest signals "no tests were collected" with this code rather than 0 or 1.
PYTEST_NO_TESTS = 5

# Scoped deliberately. A full ruff ruleset on an inherited codebase produces
# hundreds of findings that have nothing to do with the change under review,
# and a gate nobody can pass is a gate everybody disables. These three
# categories are the ones that mean "this code is broken", not "this code is
# unfashionable".
RUFF_RULES = "E9,F821,F822,F823"

# Written on the offending line to exclude a known-safe match (a test fixture,
# a documented example). Deliberately verbose so it is hard to add by accident.
ALLOW_PRAGMA = "gate:allow-secret"


@dataclass
class CheckResult:
    name: str
    passed: bool
    summary: str
    detail: str = ""
    skipped: bool = False

    @property
    def verdict(self) -> str:
        return "SKIP" if self.skipped else ("PASS" if self.passed else "FAIL")


def run(cmd: list[str], cwd: Path, timeout: int = 600) -> tuple[int, str]:
    """Run a command with no inherited proxy settings.

    Stripping the proxy variables is not tidiness: it is the second line of
    defence behind the NetworkPolicy. A test that quietly reaches the internet
    is a test whose result depends on someone else's uptime.
    """
    env = {k: v for k, v in os.environ.items()
           if k.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}}
    try:
        p = subprocess.run(
            cmd, cwd=cwd, env=env, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s: {' '.join(cmd)}"


def has_module(name: str) -> bool:
    """Is this importable by the interpreter the gate itself is running under?

    Deliberately not ``shutil.which``: a console script on PATH can belong to a
    different interpreter with a different set of installed packages, and then
    the gate reports collection errors for imports that work perfectly well.
    That is exactly the bug this project's first self-hosted run produced.
    """
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def check_lint(target: Path) -> CheckResult:
    if not shutil.which("ruff"):
        return CheckResult("lint", False, "ruff not installed", skipped=True)
    code, out = run(["ruff", "check", ".", "--select", RUFF_RULES, "--output-format", "concise"], target)
    if code == 0:
        return CheckResult("lint", True, f"no findings in {RUFF_RULES}")
    findings = [ln for ln in out.splitlines() if re.search(r":\d+:\d+:", ln)]
    return CheckResult("lint", False, f"{len(findings)} finding(s) in {RUFF_RULES}", out.strip())


def check_tests(target: Path, min_coverage: float, cov_package: str | None) -> tuple[CheckResult, CheckResult]:
    """Tests and coverage are two verdicts from one run.

    Reported separately because they fail for different reasons and deserve
    different responses: a failing test is a defect, thin coverage is a gap.
    Collapsing them into one line loses that.
    """
    if not has_module("pytest"):
        skip = CheckResult("tests", False, "pytest not importable", skipped=True)
        return skip, CheckResult("coverage", False, "no test run", skipped=True)

    # Always `sys.executable -m`, never the bare console script -- see has_module.
    cmd = [sys.executable, "-m", "pytest", "-q", "--no-header"]
    cov_json = target / ".gate-coverage.json"
    use_cov = bool(cov_package) and has_module("coverage")
    if use_cov:
        cmd = [sys.executable, "-m", "coverage", "run", "--source", cov_package,
               "-m", "pytest", "-q", "--no-header"]

    code, out = run(cmd, target)
    tail = "\n".join(out.strip().splitlines()[-12:])

    # pytest exit 5 is NO_TESTS_COLLECTED. It is deliberately a FAIL and not a
    # SKIP: an empty suite is the cheapest possible way for a coding agent to
    # turn the gate green, so "no tests" and "tests passed" must never reach
    # the same verdict. It gets its own message because the fix ("write a
    # test") is nothing like the fix for a red suite.
    if code == PYTEST_NO_TESTS:
        return (
            CheckResult("tests", False, "no tests collected — an empty suite is not a pass"),
            CheckResult("coverage", False, "no tests to measure", skipped=True),
        )

    passed = code == 0
    summary = re.search(r"(\d+ (?:passed|failed).*)$", out.strip(), re.MULTILINE)
    tests = CheckResult(
        "tests", passed,
        summary.group(1) if summary else ("exit 0" if passed else f"exit {code}"),
        "" if passed else tail,
    )

    if not use_cov:
        return tests, CheckResult("coverage", False, "coverage not measured", skipped=True)

    run([sys.executable, "-m", "coverage", "json", "-o", str(cov_json), "--quiet"], target)
    try:
        pct = json.loads(cov_json.read_text())["totals"]["percent_covered"]
    except (OSError, KeyError, json.JSONDecodeError):
        return tests, CheckResult("coverage", False, "coverage report unreadable", skipped=True)
    finally:
        cov_json.unlink(missing_ok=True)
    ok = pct >= min_coverage
    return tests, CheckResult(
        "coverage", ok, f"{pct:.1f}% against a {min_coverage:.0f}% floor",
    )


def check_no_secrets(target: Path) -> CheckResult:
    """Catch a credential the agent pasted into a file it just wrote.

    Not a substitute for real secret scanning -- it looks for the shapes that
    actually turn up in generated code (a provider key literal, an inline
    connection string with a password) in files the run touched.
    """
    patterns = {
        "provider key": re.compile(r"\b(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,})"),
        "inline dsn password": re.compile(r"://[^\s:/@]+:[^\s:/@]{6,}@"),
        "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    }
    hits: list[str] = []
    lines_cache: dict[Path, list[str]] = {}
    for path in target.rglob("*"):
        if not path.is_file() or path.stat().st_size > 512_000:
            continue
        if any(part in {".git", "node_modules", ".venv", "__pycache__"} for part in path.parts):
            continue
        if path.suffix not in {".py", ".yaml", ".yml", ".json", ".env", ".sh", ".md", ".toml", ".ts", ".js"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, rx in patterns.items():
            for m in rx.finditer(text):
                line = text[: m.start()].count("\n") + 1
                # A scanner with no way to say "this one is a fixture" gets
                # switched off within a week. The pragma is per-line and has to
                # be written next to the thing it excuses, so it shows up in
                # review rather than hiding in a config file.
                source = lines_cache.setdefault(path, text.splitlines())
                if ALLOW_PRAGMA in source[line - 1]:
                    continue
                hits.append(f"{path.relative_to(target)}:{line}: {label}")
    if hits:
        return CheckResult("secrets", False, f"{len(hits)} candidate(s)", "\n".join(hits[:20]))
    return CheckResult("secrets", True, "no credential shapes found")


def write_report(path: Path, results: list[CheckResult], target: Path) -> None:
    ran = [r for r in results if not r.skipped]
    verdict = "PASSED" if ran and all(r.passed for r in ran) else "FAILED"
    if not ran:
        verdict = "INCONCLUSIVE"
    lines = [
        "# Quality gate report",
        "",
        f"**Verdict: {verdict}**",
        "",
        f"- Target: `{target}`",
        f"- Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
        f"- Gate: `gate/run_gate.py` — deterministic, no model calls",
        "",
        "| Check | Verdict | Summary |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {r.name} | {r.verdict} | {r.summary} |" for r in results]
    for r in results:
        if r.detail:
            lines += ["", f"### {r.name}", "", "```", r.detail[:4000], "```"]
    skipped = [r.name for r in results if r.skipped]
    if skipped:
        lines += [
            "", "> Skipped checks are reported as SKIP and excluded from the verdict.",
            f"> Not run here: {', '.join(skipped)}. A skipped check is not a passed check.",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", type=Path, default=Path("."), help="repository to gate")
    ap.add_argument("--report", type=Path, default=Path("QUALITY_REPORT.md"))
    ap.add_argument("--json", type=Path, help="also write machine-readable results")
    ap.add_argument("--min-coverage", type=float, default=80.0)
    ap.add_argument("--cov-package", default=None, help="package to measure, e.g. src")
    args = ap.parse_args(argv)

    target = args.target.resolve()
    if not target.is_dir():
        print(f"gate: target is not a directory: {target}", file=sys.stderr)
        return EXIT_UNRUNNABLE

    tests, coverage = check_tests(target, args.min_coverage, args.cov_package)
    results = [check_lint(target), tests, coverage, check_no_secrets(target)]

    write_report(args.report, results, target)
    if args.json:
        args.json.write_text(json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")

    for r in results:
        print(f"{r.verdict:5} {r.name:9} {r.summary}")

    ran = [r for r in results if not r.skipped]
    if not ran:
        print("gate: every check skipped — inconclusive, not clean", file=sys.stderr)
        return EXIT_UNRUNNABLE
    return EXIT_CLEAN if all(r.passed for r in ran) else EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
