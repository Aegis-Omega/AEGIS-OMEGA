#!/usr/bin/env python3
"""Who contributed what, measured by what reached main — for every model.

  python3 scripts/contribution.py            # last 30 days
  python3 scripts/contribution.py --days 90

An agent is identified, in order, by an `Agent:` commit trailer, a
`Co-Authored-By:` trailer naming a model, or the branch prefix (codex/,
claude/, ...). Anything else is "unattributed" — that bucket is the
attribution debt to drive to zero (see AGENTS.md).

Contribution = commits that landed on main. Commits that exist only on
branches are work in progress at best and duplicated or abandoned work
at worst; they are reported, never credited.
"""
import collections
import re
import subprocess
import sys

AGENT_PREFIXES = ("claude", "codex", "copilot", "chatgpt", "qwen", "gemini", "cursor", "agent")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def agent_of(body, branches):
    m = re.search(r"^Agent:\s*(.+)$", body, re.M)
    if m:
        return m.group(1).strip()
    m = re.search(r"^Co-Authored-By:\s*([^<\n]+)", body, re.M | re.I)
    if m and "bot" not in m.group(1).lower():
        return m.group(1).strip()
    for b in branches:
        prefix = b.split("/", 1)[0]
        if prefix in AGENT_PREFIXES:
            return prefix
    return "unattributed"


def main():
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 30
    since = f"--since={days}.days"
    git("fetch", "-q", "origin", "+refs/heads/*:refs/remotes/origin/*")
    on_main = set(git("log", "origin/main", since, "--format=%H").split())

    # Branch names per commit, so commits without trailers can still be attributed.
    branches = collections.defaultdict(list)
    for ref in git("for-each-ref", "--format=%(refname:lstrip=3)", "refs/remotes/origin").split():
        if ref in ("main", "HEAD"):
            continue
        for sha in git("log", f"origin/{ref}", "--not", "origin/main", since, "--format=%H").split():
            branches[sha].append(ref)

    stats = collections.defaultdict(lambda: {"landed": 0, "branch_only": 0})
    seen = set()
    raw = git("log", "--remotes", since, "--no-merges", "--format=%H%x00%an%x00%B%x01")
    for rec in raw.split("\x01"):
        if "\x00" not in rec:
            continue
        sha, author, body = rec.strip().split("\x00", 2)
        if sha in seen or "[bot]" in author:
            continue
        seen.add(sha)
        who = agent_of(body, branches.get(sha, []))
        stats[who]["landed" if sha in on_main else "branch_only"] += 1

    total = sum(s["landed"] + s["branch_only"] for s in stats.values()) or 1
    print(f"AEGIS contribution — last {days} days (credit = commits on main)\n")
    print(f"{'agent':28} {'on main':>8} {'branch-only':>12} {'landed %':>9}")
    for who, s in sorted(stats.items(), key=lambda kv: (-kv[1]["landed"], -kv[1]["branch_only"])):
        n = s["landed"] + s["branch_only"]
        print(f"{who[:28]:28} {s['landed']:>8} {s['branch_only']:>12} {100 * s['landed'] / n:>8.1f}%")
    un = stats.get("unattributed", {"landed": 0, "branch_only": 0})
    print(f"\nunattributed: {100 * (un['landed'] + un['branch_only']) / total:.0f}% of {total} commits "
          "— every agent must add an `Agent: <model>` trailer (AGENTS.md).")


if __name__ == "__main__":
    main()
