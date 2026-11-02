#!/usr/bin/env python3
"""Classify every open PR as close / move / review / keep from git evidence (#737).

Input: a JSON list of open PRs, one object per PR with number, title, headRefName,
headRefOid, baseRefName, updatedAt (the shape of
`gh pr list --state open --limit 500 --json number,title,headRefName,headRefOid,baseRefName,updatedAt`).
The PR heads must be fetched first:
  git fetch origin main '+refs/pull/*/head:refs/remotes/pr/*'

Rules (mechanical; nothing is closed by this script):
  close  head contained in main; no changes; every changed file already identical on main;
         stacked on a deleted or closed base; or no activity for more than 21 days
  move   proof/, research/ or evidence/ lane: belongs in the lab repository (#742)
  review stacked on a live branch
  keep   active
#698 is always kept (operator rule). Closing is reversible; execute only after the
Actions billing lock (#735) is lifted.

Usage: scripts/pr-triage.py open_prs.json YYYY-MM-DD > PR_TRIAGE.tsv
"""
import datetime
import json
import subprocess
import sys

LANES = ("proof", "research", "evidence")


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def main():
    prs = json.load(open(sys.argv[1]))
    today = datetime.date.fromisoformat(sys.argv[2])
    main_sha = git("rev-parse", "origin/main")[1]
    by_head = {p["headRefName"]: p for p in prs}
    rows = {}
    for p in sorted(prs, key=lambda x: x["number"]):
        sha, base, head = p["headRefOid"], p["baseRefName"], p["headRefName"]
        updated = p["updatedAt"][:10]
        idle = (today - datetime.date.fromisoformat(updated)).days
        mb = git("merge-base", sha, main_sha)[1]
        files = git("diff", "--name-only", mb, sha)[1].splitlines() if mb else []
        same = 0
        for f in files:
            a, b = git("rev-parse", f"{sha}:{f}"), git("rev-parse", f"{main_sha}:{f}")
            same += (a[0] != 0 and b[0] != 0) or (a[0] == 0 and b[0] == 0 and a[1] == b[1])
        stacked = base != "main"
        if p["number"] == 698:
            v, why = "keep", "operator rule: do not touch #698"
        elif git("merge-base", "--is-ancestor", sha, main_sha)[0] == 0:
            v, why = "close", "head already contained in main"
        elif not files:
            v, why = "close", "no changes against main"
        elif same == len(files):
            v, why = "close", f"all {len(files)} changed files already identical on main"
        elif stacked and git("rev-parse", "--verify", "-q", "origin/" + base)[0] != 0:
            v, why = "close", f"stacked on deleted base {base}"
        elif head.split("/")[0] in LANES:
            v, why = "move", "proof/research lane: lab repository (#742)"
        elif stacked:
            v, why = "review", f"stacked on {base}"
        elif idle > 21:
            v, why = "close", f"abandoned: no activity for {idle} days (last update {updated})"
        else:
            v, why = "keep", f"active (last update {updated})"
        rows[head] = [p["number"], v, why, head, base, updated]
    changed = True
    while changed:  # a stacked PR follows its base PR
        changed = False
        for head, r in rows.items():
            b = rows.get(r[4])
            if r[1] == "review" and b and b[1] in ("close", "move"):
                r[1], r[2], changed = b[1], f"stacked on PR #{b[0]}, itself {b[1]}", True
    for r in rows.values():
        if r[1] == "review" and (today - datetime.date.fromisoformat(r[5])).days > 21:
            r[1], r[2] = "close", f"abandoned stacked PR on {r[4]} (last update {r[5]})"
    print("pr\tverdict\treason\thead\tbase\tupdated")
    for r in sorted(rows.values()):
        print("\t".join(str(x) for x in r))


if __name__ == "__main__":
    main()
