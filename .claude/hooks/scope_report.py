#!/usr/bin/env python3
"""Stop hook: report scope drift against the phase's declared targets.

Reports, deliberately — it does not block. Two reasons:

1. Scope drift needs judgement. The fix is either "this always belonged in the
   phase, add it to the targets" or "this is a different phase, revert it", and
   only a person knows which. A hard block cannot make that call.
2. A Stop hook that blocks on a condition the model cannot always clear is a
   loop. The frozen guard blocks at PreToolUse because that condition is
   unambiguous and has one correct response; this one surfaces and lets the
   human decide.

Emits a systemMessage so the drift is visible in the terminal at the moment the
turn ends, when it is still cheap to fix.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

QUIET = {"suppressOutput": True}


def emit(payload: dict) -> None:
    print(json.dumps(payload))
    sys.exit(0)


def phased_files(root: Path) -> list[Path]:
    """Root PHASED.md, plus one per immediate subdirectory.

    A repo that is one project keeps PHASED.md at the root. A repo that houses
    several — this one does — gives each its own, and each declares targets
    relative to the repo root so the diff comparison stays meaningful.
    """
    found = [root / "PHASED.md"]
    found += sorted(root.glob("*/PHASED.md"))
    return [p for p in found if p.is_file()]


def main() -> None:
    root = Path.cwd()
    checker = root / "deterministic-coding" / "phase_check.py"
    if not checker.is_file():
        emit(QUIET)

    findings: list[str] = []
    for phased in phased_files(root):
        proc = subprocess.run(
            [sys.executable, str(checker), "--repo", str(root), "--phased", str(phased)],
            capture_output=True, text=True, timeout=30,
        )
        # 0 clean, 2 could not run (no phase declared) — neither is a finding.
        if proc.returncode != 1:
            continue
        label = phased.parent.name or root.name
        body = "\n".join(
            ln for ln in proc.stdout.splitlines()
            if ln.strip() and not ln.startswith("phase_check:")
        )
        findings.append(f"[{label}]\n{body}")

    if not findings:
        emit(QUIET)
    emit({
        "suppressOutput": True,
        "systemMessage": "Phase scope check\n\n" + "\n\n".join(findings),
    })


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps(QUIET))
        sys.exit(0)
