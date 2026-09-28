---
name: list-repos
description: Report exactly which GitHub repositories this Claude Code on the web session can access right now, split into attached repos with a push branch, attached read-only repos, anonymous read-only clones on disk, and every repository reachable on request, with counts computed by script. Use this whenever the user asks what repos you have, can see, can access, have cloned or can push to; how many repositories are available; whether a particular repo is attached or pushable; or wants a map, inventory, list or visualization of their repositories. Also use it before telling anyone a repo is unavailable, and after any add_repo call, because the repository list in the system prompt is a start-of-session snapshot that goes stale.
compatibility: Claude Code on the web. Needs the Claude_Code_Remote MCP tools get_session and list_repos, plus Python 3 and git in the container.
---

# List repositories

Three different questions hide behind "what repos do you have?", and each has its own source of truth. Answer all three, because users usually mean one and need the others:

| Question | Source of truth | Why not something else |
| --- | --- | --- |
| What is attached to this session? | `get_session` → `session_context.sources` | The system prompt's repository list is written once at session start. Repos added later with `add_repo` never appear in it. |
| What can I push to? | `get_session` → `session_context.outcomes` | Attached is not the same as pushable. A repo attached for reading has no outcome branch. |
| What is actually on disk? | a scan of `/home/user` | Public repos cloned through the anonymous git proxy are on disk but never become sources. Only a scan finds them. |
| What could be attached? | `list_repos` | Everything the user's GitHub connection reaches, attached or not. |

Counts come from `scripts/inventory.py`, never from reading the tool output by eye. A list of ninety-odd repositories is easy to miscount by a handful, and the user is asking precisely because they want the number.

## Workflow

1. **Call `get_session`** with no `session_id`. Note the repos under `session_context.sources` and under `session_context.outcomes` (each outcome names a repo and the branch the session may push to).

2. **Call `list_repos`** with `limit: 200`. If the result says `has_more: true`, the listing is truncated; the script will mark the total as a floor. Use `query` to look up a specific repo that might be past the cut.

3. **Save the listing to a scratch file.** Either paste the raw JSON the tool returned, or write one line per repo in the compact form below, which is cheaper for long lists:

   ```
   owner/repo|2026-09-23|private|0
   owner/other|2025-07-05|public|1
   ```

   Fields: full name, `pushed_at` date, visibility, fork flag (1 or 0). Use the scratchpad directory from the system prompt, not the repo you are working in.

4. **Run the script:**

   ```bash
   python3 <skill-dir>/scripts/inventory.py \
     --reachable <scratch>/repos.txt \
     --sources "owner/a,owner/b,owner/c" \
     --push "owner/a,owner/b"
   ```

   It scans `/home/user` for clones (by origin URL, never by folder name), joins everything, and prints the counts, a table of every attached or on-disk repo with its branch and path, and warnings such as a repo that is attached but not yet cloned.

5. **Report.** Lead with the numbers the user asked about, then the table of attached and on-disk repos. Summarise the reachable set in one line (totals, public/private, forks, how many are stale) instead of listing all of them, unless the user asks for the full list. Relay any warning the script printed.

## Visualizing

When the user wants to see the inventory rather than read it, add `--html <scratch>/inventory.html` to the command. The page is built from `assets/inventory.html`, which already follows the Artifact page contract: tokens for both themes, phone layout, a real title. Publish it with the Artifact tool (icon `repository`).

If an inventory artifact was already published in this conversation, republish to the same file path so the link stays the same. If it came from an earlier conversation, pass its URL as `url` rather than creating a second page. The page lists private repository names, so remind the user it is private to them until they share it.

## Attaching more repositories

When the user wants a repo that is reachable but not attached:

- Call `add_repo` directly. Do not check first with curl or `git ls-remote`: private repos return 404 to anonymous requests even when the session is allowed to attach them.
- `access: "read"` on a **public** repo usually attaches nothing; the tool tells you to clone through the anonymous proxy to `/home/user/<owner>/<repo>`. That clone reads but cannot push and gets no GitHub API tools.
- A **private** repo, or `access: "push"`, attaches it as a session source; clone it to `/home/user/<repo>` as the tool instructs, then call `register_repo_root` so its CLAUDE.md and skills load.
- If a read-only clone later needs push, attach with `access: "push"` and clone fresh at the owner-less path. The two lanes use different paths on purpose; don't reuse the anonymous checkout.
- If `add_repo` refuses, relay its exact reason. The remedy is usually reconnecting GitHub at https://claude.ai/connect-github or installing the Claude GitHub App on that repository.
