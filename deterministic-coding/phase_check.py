#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Enforce the two mechanical controls in ai-coding-prompt-v2.txt.

    scope   — the diff touches only the files this phase declared
    frozen  — no file declared frozen has been modified

Both exist because the alternative is asking a reviewer to notice, and by
phase three under a deadline nobody notices. They are the cheapest possible
version of the two failure modes that actually turn up:

    scope drift   the run quietly improves things nobody asked about, and the
                  diff becomes too big to review honestly
    frozen edits  the run cannot make the suite pass, so it adjusts what
                  passing means -- the one path that has to stay closed

PHASED.md declares both, in HTML comments so they are machine-readable
without disturbing anyone reading the file:

    <!-- phase: 1 -->
    <!-- targets: gate/run_gate.py, tests/test_gate.py, deploy/**/*.yaml -->
    <!-- frozen: features/*.feature, tests/test_acceptance.py -->

Usage:
    python phase_check.py --phase 1                  # against HEAD
    python phase_check.py --phase 1 --base main      # against a branch point
    python phase_check.py --targets 'src/*.py' --frozen tests/test_api.py

Exit 0 clean, 1 a violation, 2 could not run (no phase, not a git repo).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

from pathlib import Path

EXIT_CLEAN, EXIT_VIOLATION, EXIT_UNRUNNABLE = 0, 1, 2

MARKER = re.compile(
    r"<!--\s*(?P<key>phase|targets|frozen)\s*:\s*(?P<value>.*?)\s*-->",
    re.IGNORECASE,
)


def git(*args: str, cwd: Path) -> tuple[int, str]:
    p = subprocess.run(["git", "-C", str(cwd), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def parse_phases(phased: Path) -> dict[str, dict[str, list[str]]]:
    """Read the declaration blocks out of PHASED.md.

    A `phase` marker opens a block; `targets` and `frozen` markers attach to
    the most recent one. Anything before the first `phase` marker is ignored,
    so prose at the top of the file cannot accidentally declare scope.
    """
    phases: dict[str, dict[str, list[str]]] = {}
    current: str | None = None
    for m in MARKER.finditer(phased.read_text(encoding="utf-8")):
        key, value = m.group("key").lower(), m.group("value")
        if key == "phase":
            current = value.strip()
            phases.setdefault(current, {"targets": [], "frozen": []})
        elif current is not None:
            phases[current][key] = [p.strip() for p in value.split(",") if p.strip()]
    return phases


def changed_files(base: str | None, cwd: Path) -> list[str]:
    """Files this phase touched: working tree, index, and untracked.

    Untracked files are included deliberately -- a new file nobody declared is
    scope drift just as much as an edit to an undeclared one, and it is the
    form that slips through most often.
    """
    if base:
        code, out = git("diff", "--name-only", f"{base}...HEAD", cwd=cwd)
        if code != 0:
            print(f"phase_check: cannot diff against {base!r}", file=sys.stderr)
            return []
        tracked = out.split()
    else:
        tracked = git("diff", "--name-only", "HEAD", cwd=cwd)[1].split()
    untracked = git("ls-files", "--others", "--exclude-standard", cwd=cwd)[1].split()
    return sorted(set(tracked) | set(untracked))


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a glob with the separator semantics people expect.

    Not ``fnmatch``: its ``*`` compiles to ``.*`` and therefore crosses ``/``,
    so ``src/*.py`` silently matches ``src/deep/nested.py``. A scope check that
    over-matches is worse than no scope check, because it reports clean.

        **/   zero or more path segments
        **    anything, separators included
        *     anything except a separator
        ?     one character except a separator
    """
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append(r"(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(r".*")
            i += 2
        elif pattern[i] == "*":
            out.append(r"[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append(r"[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(glob_to_regex(p).match(path) for p in patterns)


def check(targets: list[str], frozen: list[str], base: str | None, cwd: Path) -> int:
    changed = changed_files(base, cwd)
    if not changed:
        print("phase_check: nothing changed — nothing to check")
        return EXIT_CLEAN

    # Frozen first: it is the more serious of the two, and a frozen file is
    # never also a legitimate target, so reporting it twice would be noise.
    violations_frozen = [p for p in changed if matches_any(p, frozen)]
    outside = [p for p in changed
               if not matches_any(p, targets) and p not in violations_frozen]

    print(f"phase_check: {len(changed)} file(s) changed")
    if targets:
        print(f"  declared targets: {', '.join(targets)}")
    if frozen:
        print(f"  frozen:           {', '.join(frozen)}")

    if violations_frozen:
        print("\nFROZEN FILES MODIFIED — this is an escalation, not an edit:")
        for p in violations_frozen:
            print(f"  {p}")
        print("\n  The definition of done is not the run's to change. If a frozen")
        print("  test is genuinely wrong, say so and stop; a human unfreezes it.")

    if outside:
        print("\nOUTSIDE DECLARED SCOPE:")
        for p in outside:
            print(f"  {p}")
        print("\n  Either add these to the phase's targets in PHASED.md because")
        print("  they were always part of it, or revert them into their own phase.")

    if violations_frozen or outside:
        return EXIT_VIOLATION
    print("\nclean: every changed file is a declared target, no frozen file touched")
    return EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--phased", type=Path, default=None, help="default: <repo>/PHASED.md")
    ap.add_argument("--phase", help="phase id as written in the <!-- phase: --> marker")
    ap.add_argument("--base", help="compare against this ref instead of the working tree")
    ap.add_argument("--targets", help="comma-separated globs, overriding PHASED.md")
    ap.add_argument("--frozen", help="comma-separated globs, overriding PHASED.md")
    args = ap.parse_args(argv)

    repo = args.repo.resolve()
    if git("rev-parse", "--git-dir", cwd=repo)[0] != 0:
        print(f"phase_check: not a git repository: {repo}", file=sys.stderr)
        return EXIT_UNRUNNABLE

    if args.targets is not None or args.frozen is not None:
        targets = [p.strip() for p in (args.targets or "").split(",") if p.strip()]
        frozen = [p.strip() for p in (args.frozen or "").split(",") if p.strip()]
    else:
        phased = args.phased or (repo / "PHASED.md")
        if not phased.exists():
            print(f"phase_check: no {phased}; pass --targets/--frozen instead", file=sys.stderr)
            return EXIT_UNRUNNABLE
        phases = parse_phases(phased)
        if not phases:
            print(f"phase_check: {phased} declares no phases. Add:\n"
                  f"  <!-- phase: 1 -->\n  <!-- targets: path/a.py, path/b/*.yaml -->",
                  file=sys.stderr)
            return EXIT_UNRUNNABLE
        key = args.phase or list(phases)[-1]
        if key not in phases:
            print(f"phase_check: no phase {key!r} in {phased} "
                  f"(have: {', '.join(phases)})", file=sys.stderr)
            return EXIT_UNRUNNABLE
        targets, frozen = phases[key]["targets"], phases[key]["frozen"]
        print(f"phase_check: phase {key} from {phased.name}")

    if not targets:
        print("phase_check: this phase declares no targets, so nothing constrains "
              "the diff. Declare them before coding, not after.", file=sys.stderr)
        return EXIT_UNRUNNABLE

    return check(targets, frozen, args.base, repo)


if __name__ == "__main__":
    raise SystemExit(main())
