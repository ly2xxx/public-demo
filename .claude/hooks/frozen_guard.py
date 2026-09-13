#!/usr/bin/env python3
"""PreToolUse hook: refuse writes to files this phase declared frozen.

This is the difference between the workflow being a prompt and being enforced.
ai-coding-prompt-v2.txt *asks* the assistant not to edit a frozen test. This
makes the edit fail. The assistant does not decide whether to comply; the
harness declines the tool call before it runs.

Reads the hook payload on stdin, resolves the file path against the frozen
globs declared in the nearest PHASED.md, and emits a deny decision when they
match.

FAILS OPEN, deliberately and in every direction: no PHASED.md, no frozen
declaration, unparseable markers, missing phase_check, an unexpected exception
-- all allow the write. A guard that blocks edits in every repository that
never opted in would be turned off within a day, and then it protects nothing.
The cost of failing open is a missed catch; the cost of failing closed is the
whole mechanism being disabled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ALLOW = {}  # an empty object is "no opinion" — the tool call proceeds


def emit(payload: dict) -> None:
    print(json.dumps(payload))
    sys.exit(0)


def find_phased(start: Path) -> Path | None:
    """Nearest PHASED.md at or above the edited file, within the repo."""
    for d in [start, *start.parents]:
        candidate = d / "PHASED.md"
        if candidate.is_file():
            return candidate
        if (d / ".git").exists():
            break
    return None


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        emit(ALLOW)

    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw_path:
        emit(ALLOW)

    target = Path(raw_path)
    phased = find_phased(target.parent if target.parent.exists() else Path.cwd())
    if phased is None:
        emit(ALLOW)

    # phase_check owns the marker grammar and the glob semantics; importing it
    # keeps one definition of "frozen" rather than a second, drifting copy here.
    root = phased.parent
    for candidate in (root / "deterministic-coding" / "phase_check.py",
                      root.parent / "deterministic-coding" / "phase_check.py"):
        if candidate.is_file():
            sys.path.insert(0, str(candidate.parent))
            break
    else:
        emit(ALLOW)

    try:
        import phase_check  # noqa: PLC0415  (deliberately late: fail open if absent)
        phases = phase_check.parse_phases(phased)
    except Exception:
        emit(ALLOW)

    if not phases:
        emit(ALLOW)

    # The last declared phase is the one in flight. Earlier phases are closed,
    # and re-freezing their files would block legitimate later work.
    frozen = phases[list(phases)[-1]].get("frozen") or []
    if not frozen:
        emit(ALLOW)

    try:
        rel = target.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        emit(ALLOW)

    if not phase_check.matches_any(rel, frozen):
        emit(ALLOW)

    emit({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"{rel} is frozen for this phase (declared in {phased.name}).\n\n"
                "The definition of done is not this run's to change. If the frozen "
                "test is genuinely wrong, say so and stop — that is an escalation, "
                "not an edit. A human unfreezes it by editing the "
                "<!-- frozen: --> marker in PHASED.md."
            ),
        }
    })


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never let a bug in the guard block the user's work.
        print(json.dumps(ALLOW))
        sys.exit(0)
