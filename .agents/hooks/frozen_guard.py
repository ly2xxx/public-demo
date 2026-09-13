#!/usr/bin/env python3
"""Gemini/Antigravity PreToolUse hook: refuse writes to files declared frozen.

Intercepts replace_file_content, multi_replace_file_content, and write_to_file.
Reads the toolCall payload from stdin, checks against frozen globs in PHASED.md,
and emits {"decision": "deny", "reason": ...} when matched.

Fails open on any error, missing file, or unparseable marker.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ALLOW = {"decision": "allow"}


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

    tool_call = payload.get("toolCall") or {}
    args = tool_call.get("args") or {}
    raw_path = (args.get("TargetFile") or args.get("target_file") or
                args.get("file_path") or args.get("AbsolutePath"))
    if not raw_path:
        emit(ALLOW)

    target = Path(raw_path)
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()

    phased = find_phased(target.parent if target.parent.exists() else Path.cwd())
    if phased is None:
        emit(ALLOW)

    root = phased.parent
    for candidate in (root / "deterministic-coding" / "phase_check.py",
                      root.parent / "deterministic-coding" / "phase_check.py"):
        if candidate.is_file():
            sys.path.insert(0, str(candidate.parent))
            break
    else:
        emit(ALLOW)

    try:
        import phase_check  # noqa: PLC0415
        phases = phase_check.parse_phases(phased)
    except Exception:
        emit(ALLOW)

    if not phases:
        emit(ALLOW)

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
        "decision": "deny",
        "reason": (
            f"{rel} is frozen for this phase (declared in {phased.name}).\n\n"
            "The definition of done is not this run's to change. If the frozen "
            "test is genuinely wrong, say so and stop — that is an escalation, "
            "not an edit. A human unfreezes it by editing the "
            "<!-- frozen: --> marker in PHASED.md."
        ),
    })


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps(ALLOW))
        sys.exit(0)
