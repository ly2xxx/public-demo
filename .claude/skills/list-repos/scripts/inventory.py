#!/usr/bin/env python3
"""Exact repository inventory for a Claude Code on the web session.

Three sources each see part of the picture, and none of them alone is the answer:

  --reachable FILE  list_repos output. Either the raw JSON the tool returned, or one
                    `owner/repo|pushed_at|visibility|fork` line per repository.
  --sources LIST    get_session -> session_context.sources (URLs or owner/repo, comma separated).
                    These are the repos attached to the session, including ones added mid-session.
  --push LIST       get_session -> session_context.outcomes repos (comma separated).
                    These have a designated branch the session may push to.

The script also scans --root (default /home/user) for git clones, which is the only way to
see anonymous read-only clones of public repos: they are on disk but never become sources.

Prints exact counts and a table of every repo that is attached or on disk.
--html OUT renders the inventory page from assets/inventory.html.
"""
import argparse
import collections
import datetime
import json
import os
import re
import subprocess
import sys

TIERS = ("push", "attached", "clone", "reachable")
TIER_LABEL = {
    "push": "push branch",
    "attached": "attached",
    "clone": "anonymous clone",
    "reachable": "reachable",
}


def repo_key(value):
    """Normalise a GitHub URL or owner/repo string to lowercase owner/repo."""
    value = value.strip().rstrip("/")
    if not value:
        return ""
    value = re.sub(r"\.git$", "", value)
    value = re.sub(r"^git@[^:]+:", "", value)
    parts = [p for p in re.split(r"[/:]", value) if p]
    return "/".join(parts[-2:]).lower() if len(parts) >= 2 else ""


def split_list(raw):
    return [k for k in (repo_key(v) for v in (raw or "").split(",")) if k]


def load_reachable(path):
    """Return (rows keyed by repo, has_more flag). Accepts list_repos JSON or pipe lines."""
    text = open(path, encoding="utf-8").read().strip()
    rows, has_more = {}, False
    if text.startswith("{") or text.startswith("["):
        data = json.loads(text)
        items = data.get("repos", []) if isinstance(data, dict) else data
        has_more = bool(data.get("has_more")) if isinstance(data, dict) else False
        for r in items:
            name = r.get("full_name", "")
            rows[repo_key(name)] = {
                "name": name,
                "pushed": (r.get("pushed_at") or "")[:10],
                "visibility": r.get("visibility", "unknown"),
                "fork": bool(r.get("fork")),
            }
    else:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            f = (line.split("|") + ["", "", "", ""])[:4]
            rows[repo_key(f[0])] = {
                "name": f[0],
                "pushed": f[1][:10],
                "visibility": f[2] or "unknown",
                "fork": f[3].strip().lower() in ("1", "true", "yes", "fork"),
            }
    return rows, has_more


def git(path, *args):
    try:
        out = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=20)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def disk_size(path):
    try:
        out = subprocess.run(["du", "-sh", path], capture_output=True, text=True, timeout=60)
        return out.stdout.split()[0] if out.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return ""


def scan_disk(root, max_depth):
    """Find git clones under root. Trust the origin URL, never the directory name."""
    found = {}
    root = os.path.abspath(root)
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, _ in os.walk(root):
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        if os.path.exists(os.path.join(dirpath, ".git")):
            key = repo_key(git(dirpath, "remote", "get-url", "origin"))
            if key and key not in found:
                found[key] = {
                    "path": dirpath,
                    "branch": git(dirpath, "rev-parse", "--abbrev-ref", "HEAD"),
                    "size": disk_size(dirpath),
                }
            dirnames[:] = []  # a clone's own subdirectories are not separate clones
            continue
        if depth >= max_depth:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
    return found


def age_days(pushed, as_of):
    try:
        return (as_of - datetime.date.fromisoformat(pushed)).days
    except ValueError:
        return None


def build(args):
    as_of = datetime.date.fromisoformat(args.as_of) if args.as_of else datetime.date.today()
    reachable, has_more = load_reachable(args.reachable) if args.reachable else ({}, False)
    sources, push = set(split_list(args.sources)), set(split_list(args.push))
    disk = {} if args.no_scan else scan_disk(args.root, args.depth)

    rows = []
    for key in sorted(set(reachable) | sources | push | set(disk)):
        base = reachable.get(key, {})
        d = disk.get(key, {})
        if key in push:
            tier = "push"
        elif key in sources:
            tier = "attached"
        elif d:
            tier = "clone"
        else:
            tier = "reachable"
        pushed = base.get("pushed", "")
        rows.append({
            "n": base.get("name") or key,
            "d": pushed,
            "v": base.get("visibility", "unknown"),
            "f": int(base.get("fork", False)),
            "a": age_days(pushed, as_of),
            "t": tier,
            "p": d.get("path", ""),
            "b": d.get("branch", ""),
            "z": d.get("size", ""),
            "listed": key in reachable,
        })

    warnings = []
    if has_more:
        warnings.append("list_repos reported has_more=true: the reachable count is a floor, not a total.")
    for r in rows:
        if r["t"] in ("push", "attached") and not r["p"]:
            warnings.append(f"{r['n']} is attached but not cloned on disk yet.")
        # A truncated listing is expected to miss repos, so absence only means something when it is complete.
        if not r["listed"] and args.reachable and not has_more:
            warnings.append(f"{r['n']} is on disk or attached but absent from list_repos.")
    return rows, warnings, as_of, has_more


def summarise(rows, warnings, as_of, has_more):
    listed = [r for r in rows if r["listed"]]
    count = collections.Counter(r["t"] for r in rows)
    vis = collections.Counter(r["v"] for r in listed)
    forks = sum(r["f"] for r in listed)
    stale = sum(1 for r in listed if r["a"] is not None and r["a"] > 365)
    fresh = sum(1 for r in listed if r["a"] is not None and r["a"] <= 30)
    floor = "+" if has_more else ""

    def names(tier):
        return ", ".join(r["n"].split("/", 1)[-1] for r in rows if r["t"] == tier) or "-"

    out = [f"Repository inventory, as of {as_of.isoformat()}", ""]
    out.append(f"  attached to session  {count['push'] + count['attached']}")
    out.append(f"    with push branch   {count['push']}   {names('push')}")
    out.append(f"    read only          {count['attached']}   {names('attached')}")
    out.append(f"  anonymous clones     {count['clone']}   {names('clone')}")
    out.append(f"  reachable on request {len(listed)}{floor}  "
               f"({vis.get('public', 0)} public, {vis.get('private', 0)} private, "
               f"{forks} fork{'' if forks == 1 else 's'})")
    out.append(f"  pushed in last 30d   {fresh}")
    out.append(f"  untouched > 1 year   {stale}")
    out.append("")

    live = [r for r in rows if r["t"] != "reachable"]
    if live:
        w = max(len(r["n"]) for r in live)
        out.append(f"  {'TIER':<16} {'REPO':<{w}}  {'BRANCH':<30} PATH")
        for r in sorted(live, key=lambda r: (TIERS.index(r["t"]), r["n"].lower())):
            out.append(f"  {TIER_LABEL[r['t']]:<16} {r['n']:<{w}}  {r['b'] or '-':<30} "
                       f"{r['p'] or 'not cloned'}{'  (' + r['z'] + ')' if r['z'] else ''}")
    if warnings:
        out.append("")
        out.extend(f"  ! {w}" for w in warnings)
    return "\n".join(out)


def render_html(rows, as_of, title, template_path, out_path):
    owners = collections.Counter(r["n"].split("/")[0] for r in rows if r["listed"])
    if not title:
        title = f"{owners.most_common(1)[0][0]} Repo Inventory" if owners else "Repo Inventory"
    data = sorted(rows, key=lambda r: (r["a"] is None, r["a"] if r["a"] is not None else 0))
    html = open(template_path, encoding="utf-8").read()
    html = (html.replace("__TITLE__", title)
                .replace("__ASOF__", as_of.strftime("%-d %b %Y"))
                .replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/")))
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return title


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reachable", help="file holding list_repos output (JSON or pipe lines)")
    ap.add_argument("--sources", default="", help="session_context.sources, comma separated")
    ap.add_argument("--push", default="", help="session_context.outcomes repos, comma separated")
    ap.add_argument("--root", default="/home/user", help="directory to scan for clones")
    ap.add_argument("--depth", type=int, default=3, help="how deep to look for clones under --root")
    ap.add_argument("--no-scan", action="store_true", help="skip the on-disk scan")
    ap.add_argument("--as-of", help="YYYY-MM-DD used for ages (default: today)")
    ap.add_argument("--html", help="write the inventory page to this path")
    ap.add_argument("--title", help="page title (default: '<main owner> Repo Inventory')")
    ap.add_argument("--template", default=os.path.join(here, "..", "assets", "inventory.html"))
    args = ap.parse_args()

    rows, warnings, as_of, has_more = build(args)
    print(summarise(rows, warnings, as_of, has_more))
    if args.html:
        title = render_html(rows, as_of, args.title, args.template, args.html)
        print(f"\n  page written: {args.html}  (title: {title})")


if __name__ == "__main__":
    sys.exit(main())
