# Enforcing the workflow

`deterministic-coding/ai-coding-prompt-v2.txt` is a prompt. A prompt is advice:
the assistant reads it and mostly complies. These hooks are the harness — it
declines the tool call before it runs, and compliance is not the assistant's to
decide.

That distinction is the whole point of the v2 changelog. v1 *asked* the
assistant not to run tests, and the assistant ran them within minutes.

| Control | Mechanism | Behaviour |
| --- | --- | --- |
| Frozen files | `PreToolUse` on `Edit\|Write\|MultiEdit\|NotebookEdit` | **Blocks.** The write fails with a reason telling the assistant to escalate. |
| Scope drift | `Stop` | **Reports.** Prints the offending files when the turn ends. |

Frozen files block because the condition is unambiguous and has exactly one
correct response. Scope drift only reports, for two reasons: the fix needs
judgement (add to targets, or revert into its own phase), and a `Stop` hook
that blocks on a condition the model cannot always clear is an infinite loop.

Both **fail open** — no `PHASED.md`, no `<!-- frozen: -->` declaration,
unparseable markers, a missing `phase_check.py`, any unexpected exception: the
tool call proceeds. A guard that blocks edits in repositories that never opted
in gets switched off within a day, and then it protects nothing.

## Three scopes, weakest to strongest

**1. This repository (what is configured here).** `.claude/settings.json` is
committed, so the hooks apply to every session in this repo on any machine —
including Claude Code on the web, which is where they were built. Nothing to
install. This is the right default: the rules travel with the code they govern,
and they are reviewable in a diff.

**2. This machine, every project.** Copy the same `hooks` block into
`~/.claude/settings.json` and point the commands at an absolute path (there is
no `$CLAUDE_PROJECT_DIR` outside a project). Per-machine, not per-account —
`~/.claude/` is a local directory, so this needs repeating on each machine or
keeping in dotfiles.

**3. Every session under the account.** Package the hooks as a **plugin** and
enable it on claude.ai. Plugins enabled there sync down to every session signed
into the account (`syncClaudeAiPlugins`, on by default), which is the only route
that genuinely follows the account rather than the machine. A *skill* also
syncs this way, but a skill is advisory — only a plugin can carry hooks, and
hooks are the part that enforces.

To go that route: put `plugin.json`, `hooks/`, and the prompt as a skill in a
repo, register it as a marketplace, install, enable. Worth doing once the
workflow has stopped changing; while it is still on v2 and moving, the
repo-scoped version is easier to iterate on.

**Not available:** there is no server-side account setting that pushes hooks to
every machine directly. Organisation-wide enforcement is a separate mechanism —
managed settings, deployed by an admin, which can also pin `claudeMd` and set
`allowManagedHooksOnly` so only the organisation's hooks run. That is the
enterprise answer, not the individual one.

## Verifying

```bash
# frozen guard — should print a deny decision for a frozen path
echo '{"tool_name":"Edit","tool_input":{"file_path":"'$PWD'/AI-SDLC/gate/run_gate.py"}}' \
  | python3 .claude/hooks/frozen_guard.py

# scope report — quiet when clean, prints the drift when not
python3 .claude/hooks/scope_report.py < /dev/null
```

If a hook does not fire in a session that was already running when
`.claude/settings.json` first appeared, the settings watcher has not picked the
directory up. Open `/hooks` once to reload, or restart the session.
