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


def _valid_pr_record(p):
    return (isinstance(p, dict) and type(p.get("n")) is int and p["n"] > 0
            and isinstance(p.get("t"), str) and isinstance(p.get("h"), str) and bool(p["h"])
            and isinstance(p.get("b"), str) and bool(p["b"])
            and isinstance(p.get("s"), str)
            and bool(re.fullmatch(r"[0-9a-f]{40}", p["s"])))


def open_prs(quick=False):
    """Never certify a partially fetched PR list as the whole board."""
    cache = os.path.join(git_dir(), "aegis-open-prs.json")
    try:
        if time.time() - os.path.getmtime(cache) < CACHE_TTL:
            with open(cache) as f:
                saved = json.load(f)
            # Legacy plain-list caches may have been truncated by failed paging.
            # Only trust snapshots recorded AFTER the completeness repair.
            records = saved.get("prs") if isinstance(saved, dict) else None
            if (isinstance(saved, dict)
                    and saved.get("format") == "AEGIS_PR_SNAPSHOT_V2"
                    and saved.get("complete") is True
                    and isinstance(records, list) and records
                    and all(_valid_pr_record(p) for p in records)):
                return records, "cache"
    except (OSError, ValueError, TypeError):
        pass
    if quick:
        return [], "unavailable"  # Hook only trusts a fresh full cache.
    prs = []
    complete = False
    for page in range(1, 20):
        out = sh("gh", "api",
                 f"repos/{REPO}/pulls?state=open&per_page=100&page={page}",
                 "--jq", ".[] | {n: .number, t: .title, h: .head.ref, b: .base.ref, d: .created_at[:10], s: .head.sha}")
        if not out.strip():
            break  # Ambiguous final page or failed request: status stays UNKNOWN.
        try:
            batch = [json.loads(line) for line in out.splitlines() if line.strip()]
        except (TypeError, ValueError):
            break
        if not batch or len(batch) > 100 or not all(_valid_pr_record(p) for p in batch):
            break
        prs.extend(batch)
        if len(batch) < 100:
            complete = True
            break
    if complete:
        try:
            with open(cache, "w") as f:
                json.dump({"format": "AEGIS_PR_SNAPSHOT_V2",
                           "complete": True, "prs": prs}, f)
        except OSError:
            pass
        return prs, "github"
    if prs:
        return prs, "partial"
    heads = sh("git", "ls-remote", "--heads", "origin", timeout=30)
    branches = [{"n": None, "t": "", "h": line.split("refs/heads/", 1)[1],
                 "b": "?", "d": ""}
                for line in heads.splitlines()
                if "refs/heads/" in line and not line.endswith("/main")]
    return branches, "branches" if branches else "unavailable"


def open_issue_board(timeout=15):
    """Read the shared work board. API failure is UNKNOWN, never an empty board.

    Search excludes pull requests, unlike GitHub's /issues endpoint. The
    returned source distinguishes a complete set from a truncated search.
    No issue claim is auto-expired here: doing so requires reviewing the actual
    comment history and current ownership.
    """
    from urllib.parse import quote

    query = quote(f"repo:{REPO} is:issue is:open", safe="")
    endpoint = f"search/issues?q={query}&per_page=100"
    jq = "{total: .total_count, incomplete: .incomplete_results, items: [.items[] | {n: .number, t: .title, labels: [.labels[].name]}]}"
    raw = sh("gh", "api", endpoint, "--jq", jq, timeout=timeout)
    if not raw.strip():
        return [], "unavailable"
    try:
        payload = json.loads(raw)
        total = payload["total"]
        issues = payload["items"]
        incomplete = payload.get("incomplete")
        if type(total) is not int or total < 0 or not isinstance(issues, list):
            raise ValueError("Invalid issue search result")
        for issue in issues:
            if (not isinstance(issue, dict) or type(issue.get("n")) is not int
                    or not isinstance(issue.get("t"), str)
                    or not isinstance(issue.get("labels"), list)
                    or any(not isinstance(x, str) for x in issue["labels"])):
                raise ValueError("Malformed issue record")
        return issues, "github" if incomplete is False and len(issues) == total else "partial"
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return [], "unavailable"


def relevant_issues(issues, query, limit=8):
    """Prefer explicit #issue IDs; other matches are advisory title keywords."""
    keys = words(query)
    explicit = {int(n) for n in re.findall(r"(?<!\w)#(\d+)", query)}
    found = []
    for issue in issues:
        matched = sorted(keys & words(issue["t"]))
        if issue["n"] in explicit or len(matched) >= 2:
            found.append((issue["n"] in explicit, len(matched), issue, matched))
    found.sort(key=lambda x: (-int(x[0]), -x[1], x[2]["n"]))
    return [(issue, matched) for _, _, issue, matched in found[:limit]]


def holon_disposition(pr_source, issue_source, pr_hits, issue_hits):
    """Informational work allocation ONLY; never an execution authorization."""
    if pr_source not in ("github", "cache") or issue_source != "github":
        return "HOLD_INCOMPLETE_SHARED_STATE"
    if any("needs-operator" in issue["labels"] for issue, _ in issue_hits):
        return "OPERATOR_ACTION_REQUIRED"
    if any("claimed" in issue["labels"] for issue, _ in issue_hits):
        return "HOLD_CLAIMED_WORK_COORDINATE"
    if pr_hits:
        return "REVIEW_EXISTING_PR_FIRST"
    return "ISSUE_ASSIGNMENT_AND_REVIEW_REQUIRED"


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
    """True if annotated billing lock, False if checked, None if indeterminate."""
    newest = max((p for p in prs if _valid_pr_record(p)),
                 key=lambda p: p["n"], default=None)
    if newest is None:
        return None
    out = sh("gh", "api", f"repos/{REPO}/commits/{newest['s']}/check-runs?per_page=100",
             "--jq", '.check_runs[] | select(.conclusion=="failure") | .id')
    run_ids = out.split()
    if not run_ids or any(not i.isdigit() for i in run_ids):
        return None
    for run_id in run_ids[:3]:
        annotation = sh("gh", "api", f"repos/{REPO}/check-runs/{run_id}/annotations")
        if not annotation.strip():
            return None
        if "locked due to a billing issue" in annotation.lower():
            return True
    return False if len(run_ids) <= 3 else None


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
    quick = "--quick" in sys.argv
    args = [a for a in sys.argv[1:] if a not in ("--json", "--quick")]
    query = " ".join(args)
    if not quick:
        sh("git", "fetch", "-q", "origin", "main", timeout=20)
    sha, _, date = sh("git", "log", "-1", "--format=%h %cs", "origin/main").strip().partition(" ")
    age = sh("git", "log", "-1", "--format=%ct", "origin/main").strip()
    age_days = int((time.time() - int(age)) / 86400) if age else None
    branch = sh("git", "branch", "--show-current").strip() or "(detached)"
    behind = sh("git", "rev-list", "--count", "HEAD..origin/main").strip() or "?"
    prs, source = open_prs(quick=quick)
    issues, issue_source = open_issue_board(timeout=4 if quick else 15)
    stacked = [p for p in prs if p["b"] not in ("main", "?")]
    locked = (billing_locked(prs) if not quick and source in ("github", "cache") else None)
    hits = overlaps(prs, query)
    issue_hits = relevant_issues(issues, query)
    disposition = holon_disposition(source, issue_source, hits, issue_hits)
    p0 = [issue for issue in issues if "p0" in issue["labels"]]
    code = existing_code(query) if query and not quick else []

    if "--json" in sys.argv:
        print(json.dumps({"main": sha, "main_date": date, "main_age_days": age_days,
                          "branch": branch, "behind_main": behind,
                          "open": len(prs) if source in ("github", "cache") else None,
                          "stacked": len(stacked) if source in ("github", "cache") else None,
                          "source": source, "ci_billing_locked": locked,
                          "issue_source": issue_source,
                          "issue_count": len(issues) if issue_source == "github" else None,
                          "holon_disposition": disposition,
                          "p0_issues": [{"number": i["n"], "title": i["t"], "labels": i["labels"]}
                                        for i in p0],
                          "issue_matches": [{"number": i["n"], "title": i["t"],
                                             "labels": i["labels"], "match": m}
                                            for i, m in issue_hits],
                          "overlaps": [{"pr": p["n"], "title": p["t"], "head": p["h"],
                                        "base": p["b"], "match": m} for _, p, m in hits],
                          "existing_code": [{"path": c, "match": m} for c, m in code]}))
        return

    kind = "open PRs" if source in ("github", "cache") else "remote branches (not a complete PR list)"
    lines = [f"AEGIS REPO STATE (measured now, not from docs)",
             f"- main = {sha} from {date} ({age_days} days old). You are on '{branch}', {behind} behind main."]
    if quick:
        lines.append("- QUICK: bounded 4s issue lookup; PRs only from fresh cache; run full preflight before editing.")
    if source in ("github", "cache"):
        lines.append(f"- {len(prs)} {kind}; {len(stacked)} stacked on non-main bases.")
    else:
        lines.append("- OPEN PR COUNT UNKNOWN: GitHub list unavailable. Remote branches cannot establish issue/PR state.")
    if issue_source == "github":
        lines.append(f"- Issue board: {len(issues)} open issues ({len(p0)} P0); claims are advisory, not auto-expired.")
        for i in p0[:8]:
            labels = ", ".join(i["labels"])
            lines.append(f"  P0 #{i['n']} {i['t'][:100]} [{labels}]")
    else:
        lines.append("- ISSUE BOARD UNKNOWN/PARTIAL: do not assume an unclaimed task.")
    if issue_hits:
        lines.append("- Related issues (check owners/claims; coordinate before editing):")
        for issue, matched in issue_hits:
            lines.append(f"  #{issue['n']} {issue['t'][:100]} [labels: {', '.join(issue['labels'])}] (match: {', '.join(matched)})")
    lines.append(f"- Holon coordination: {disposition}. Informational only; never authorizes a merge/release.")
    if locked:
        lines.append("- CI IS NOT RUNNING: GitHub Actions jobs fail with 'account is locked due to a "
                     "billing issue'. Every red check is that lock, not your code. Do NOT open PRs to "
                     "'fix' CI; nothing can be verified or merged until the operator fixes org billing.")
    if age_days is not None and age_days > 7 and source in ("github", "cache") and len(prs) > 20:
        lines.append("- main is stale and the queue is huge: the work you are about to do may "
                     "already exist in an open PR. Check the list below before writing code.")
    if hits:
        lines.append("- Open work that overlaps this task (read it, extend it or say why not; do not rebuild it):")
        for _, p, m in hits:
            ref = f"#{p['n']}" if p["n"] else "branch"
            base = "" if p["b"] in ("main", "?") else f" [stacked on {p['b']}]"
            lines.append(f"  {ref} {p['h']}{base} — {p['t'][:90]} (match: {', '.join(m)})")
    elif query:
        lines.append("- No *title-keyword* PR overlap found in available data; code and file-path overlap NOT ruled out.")
    if code:
        lines.append("- Code already on main that matches this task (read it first; reuse or extend it):")
        for path, m in code:
            lines.append(f"  {path} (match: {', '.join(m)})")
    lines.append("- Rules: branch only from origin/main; PR base must be main; one PR per task. "
                 "Docs (HANDOFF/INDEX/CLAUDE.md) may be stale — the commands above are not.")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
