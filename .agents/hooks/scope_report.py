#!/usr/bin/env python3
"""Gemini/Antigravity Stop hook: report scope drift against the phase's declared targets.

Reports scope drift when Gemini finishes an execution loop.
On the first stop attempt (executionNum == 1), if drift is found, it returns
{"decision": "continue", "reason": ...} so Gemini is warned and can correct or explain.
On subsequent attempts (executionNum > 1), it allows stopping to avoid infinite loops.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ALLOW = {"decision": "allow"}


def emit(payload: dict) -> None:
    print(json.dumps(payload))
    sys.exit(0)


def find_repo_root() -> Path:
    """Resolve the repository root containing .git."""
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for p in [start, *start.parents]:
            if (p / ".git").exists():
                return p
    return Path.cwd()


def phased_files(root: Path) -> list[Path]:
    """Root PHASED.md, plus one per immediate subdirectory."""
    found = [root / "PHASED.md"]
    found += sorted(root.glob("*/PHASED.md"))
    return [p for p in found if p.is_file()]


def main() -> None:
    exec_num = 1
    try:
        if not sys.stdin.isatty():
            payload = json.load(sys.stdin)
            exec_num = payload.get("executionNum", 1)
    except Exception:
        pass

    root = find_repo_root()
    checker = root / "deterministic-coding" / "phase_check.py"
    if not checker.is_file():
        emit(ALLOW)

    findings: list[str] = []
    for phased in phased_files(root):
        proc = subprocess.run(
            [sys.executable, str(checker), "--repo", str(root), "--phased", str(phased)],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 1:
            continue
        label = phased.parent.name or root.name
        body = "\n".join(
            ln for ln in proc.stdout.splitlines()
            if ln.strip() and not ln.startswith("phase_check:")
        )
        findings.append(f"[{label}]\n{body}")

    if not findings:
        emit(ALLOW)

    # Warn once on first stop attempt; allow stopping on subsequent attempts.
    if exec_num == 1:
        emit({
            "decision": "continue",
            "reason": "Phase scope check warning:\n\n" + "\n\n".join(findings),
        })
    else:
        emit(ALLOW)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps(ALLOW))
        sys.exit(0)
