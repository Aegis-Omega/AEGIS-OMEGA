#!/usr/bin/env python3
"""Real repo state for an agent, before it writes anything.

Why: main stopped moving while hundreds of PRs stayed open. Every new agent
starts from main, cannot see the open work, and rebuilds it on yet another
branch. This prints what main is, how old it is, how big the open-PR queue is,
and which open PRs already overlap the task text given as argv.

  python3 scripts/agent_context.py "fix vercel build for hub"
  python3 scripts/agent_context.py --json "..."

Read-only. PR list comes from the GitHub REST API via `gh api` (cached 10 min
in .git/); without gh it falls back to remote branch names.
"""
import json
import os
import re
import subprocess
import sys
import time

REPO = "Aegis-Omega/AEGIS-OMEGA"
CACHE_TTL = 600
STOP = set("""the and for with from into onto that this then than when what have has
add fix feat make made new use using update all any can not but are was were will
should would could please just also more some like need want here there them they
v1 v2 v3 main branch code repo file files""".split())


def sh(*argv, timeout=30):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def git_dir():
    return sh("git", "rev-parse", "--absolute-git-dir").strip() or ".git"


def open_prs():
    cache = os.path.join(git_dir(), "aegis-open-prs.json")
    try:
        if time.time() - os.path.getmtime(cache) < CACHE_TTL:
            with open(cache) as f:
                return json.load(f), "cache"
    except (OSError, ValueError):
        pass
    # Manual paging: gh --paginate follows numeric-id Link URLs some proxies refuse.
    prs = []
    for page in range(1, 20):
        out = sh("gh", "api", f"repos/{REPO}/pulls?state=open&per_page=100&page={page}",
                 "--jq", ".[] | {n: .number, t: .title, h: .head.ref, b: .base.ref, d: .created_at[:10], s: .head.sha}")
        batch = [json.loads(l) for l in out.splitlines() if l.strip()]
        prs += batch
        if len(batch) < 100:
            break
    if prs:
        try:
            with open(cache, "w") as f:
                json.dump(prs, f)
        except OSError:
            pass
        return prs, "github"
    heads = sh("git", "ls-remote", "--heads", "origin", timeout=30)
    prs = [{"n": None, "t": "", "h": l.split("refs/heads/", 1)[1], "b": "?", "d": ""}
           for l in heads.splitlines() if "refs/heads/" in l and not l.endswith("/main")]
    return prs, "branches"


def existing_code(query, limit=8):
    """Code on origin/main that matches the task's words.

    Open PRs are only half of "what exists": most of the system is already on
    main. Rare words weigh more than common ones (inverse document frequency),
    a word in the file path weighs extra, and docs are left out.
    """
    import math
    q = sorted(words(query), key=len, reverse=True)[:10]
    if not q:
        return []
    hits = {}
    for w in q:
        out = sh("git", "grep", "-l", "-i", "-I", "-e", w, "origin/main", "--",
                 "*.py", "*.ts", "*.tsx", "*.mjs", "*.js", "*.rs", "*.go",
                 ":!*node_modules*", ":!*.min.js", ":!*/dist/*", timeout=20)
        hits[w] = [l.split(":", 1)[1] for l in out.splitlines() if ":" in l]
    score = {}
    for w, files in hits.items():
        if not files:
            continue
        weight = 1 / math.log(len(files) + 2)
        for f in files:
            m = score.setdefault(f, [0.0, set()])
            m[0] += weight * (3 if w in f.lower() else 1)
            m[1].add(w)
    ranked = sorted(score.items(), key=lambda kv: -kv[1][0])
    return [(f, sorted(ws)) for f, (sc, ws) in ranked if len(ws) >= min(2, len(q))][:limit]


def billing_locked(prs):
    """True when GitHub refuses to start Actions jobs for the account.

    Then every check is red without running, and "fixing CI" in code is wasted work.
    """
    newest = max((p for p in prs if p.get("s")), key=lambda p: p["n"], default=None)
    if not newest:
        return False
    out = sh("gh", "api", f"repos/{REPO}/commits/{newest['s']}/check-runs?per_page=100",
             "--jq", '.check_runs[] | select(.conclusion=="failure") | .id')
    for run_id in out.split()[:3]:
        if "locked due to a billing issue" in sh("gh", "api", f"repos/{REPO}/check-runs/{run_id}/annotations"):
            return True
    return False


def words(s):
    return {w for w in re.findall(r"[a-z0-9]{3,}", s.lower().replace("-", " ").replace("_", " "))
            if w not in STOP and not w.isdigit()}


def overlaps(prs, query, limit=8):
    q = words(query)
    if not q:
        return []
    scored = []
    for p in prs:
        hit = q & words(p["t"] + " " + p["h"])
        if len(hit) >= 2 or (len(q) <= 2 and hit):
            scored.append((len(hit), p, sorted(hit)))
    scored.sort(key=lambda x: (-x[0], -(x[1]["n"] or 0)))
    return scored[:limit]


def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    query = " ".join(args)
    sh("git", "fetch", "-q", "origin", "main", timeout=20)
    sha, _, date = sh("git", "log", "-1", "--format=%h %cs", "origin/main").strip().partition(" ")
    age = sh("git", "log", "-1", "--format=%ct", "origin/main").strip()
    age_days = int((time.time() - int(age)) / 86400) if age else None
    branch = sh("git", "branch", "--show-current").strip() or "(detached)"
    behind = sh("git", "rev-list", "--count", "HEAD..origin/main").strip() or "?"
    prs, source = open_prs()
    stacked = [p for p in prs if p["b"] not in ("main", "?")]
    locked = billing_locked(prs)
    hits = overlaps(prs, query)
    code = existing_code(query) if query else []

    if "--json" in sys.argv:
        print(json.dumps({"main": sha, "main_date": date, "main_age_days": age_days,
                          "branch": branch, "behind_main": behind, "open": len(prs),
                          "stacked": len(stacked), "source": source, "ci_billing_locked": locked,
                          "overlaps": [{"pr": p["n"], "title": p["t"], "head": p["h"],
                                        "base": p["b"], "match": m} for _, p, m in hits],
                          "existing_code": [{"path": c, "match": m} for c, m in code]}))
        return

    kind = "open PRs" if source != "branches" else "remote branches (gh unavailable)"
    lines = [f"AEGIS REPO STATE (measured now, not from docs)",
             f"- main = {sha} from {date} ({age_days} days old). You are on '{branch}', {behind} behind main.",
             f"- {len(prs)} {kind}; {len(stacked)} are stacked on non-main bases."]
    if locked:
        lines.append("- CI IS NOT RUNNING: GitHub Actions jobs fail with 'account is locked due to a "
                     "billing issue'. Every red check is that lock, not your code. Do NOT open PRs to "
                     "'fix' CI; nothing can be verified or merged until the operator fixes org billing.")
    if age_days is not None and age_days > 7 and len(prs) > 20:
        lines.append("- main is stale and the queue is huge: the work you are about to do may "
                     "already exist in an open PR. Check the list below before writing code.")
    if hits:
        lines.append("- Open work that overlaps this task (read it, extend it or say why not; do not rebuild it):")
        for _, p, m in hits:
            ref = f"#{p['n']}" if p["n"] else "branch"
            base = "" if p["b"] in ("main", "?") else f" [stacked on {p['b']}]"
            lines.append(f"  {ref} {p['h']}{base} — {p['t'][:90]} (match: {', '.join(m)})")
    elif query:
        lines.append("- No open PR/branch overlaps this task by keyword.")
    if code:
        lines.append("- Code already on main that matches this task (read it first; reuse or extend it):")
        for path, m in code:
            lines.append(f"  {path} (match: {', '.join(m)})")
    lines.append("- Rules: branch only from origin/main; PR base must be main; one PR per task. "
                 "Docs (HANDOFF/INDEX/CLAUDE.md) may be stale — the commands above are not.")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
