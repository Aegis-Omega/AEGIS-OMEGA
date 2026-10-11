#!/usr/bin/env python3
"""AEGIS issue delivery gate. Read-only, fail-closed, no dynamic code execution.

It checks one PR against a machine-readable GitHub Issue contract and live,
exact-head GitHub evidence. A positive finding means only that enumerated gates
are satisfied; it is NOT branch protection, provenance signing or merge authority.
"""
import argparse
import fnmatch
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCHEMA = "aegis.issue-work.v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
MARKER = re.compile(r"<!--\s*AEGIS_WORK_V1\s*(.*?)\s*-->", re.S)
ISSUE_LINK = re.compile(r"(?mi)^AEGIS-WORK-ISSUE:\s*#([1-9][0-9]*)\s*$")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
APPROVAL_STATES = {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"}


class Invalid(Exception):
    pass


def require(test, reason):
    if not test:
        raise Invalid(reason)


def contract_from_body(body):
    require(isinstance(body, str), "ISSUE_BODY_MISSING")
    blocks = MARKER.findall(body)
    require(len(blocks) == 1, "CONTRACT_MARKER_MISSING_OR_DUPLICATED")
    try:
        c = json.loads(blocks[0])
    except (TypeError, ValueError) as exc:
        raise Invalid("CONTRACT_JSON_INVALID") from exc
    require(isinstance(c, dict) and c.get("schema") == SCHEMA, "CONTRACT_SCHEMA_INVALID")
    require(isinstance(c.get("objective"), str) and len(c["objective"].strip()) >= 16,
            "OBJECTIVE_UNSPECIFIED")
    require(c.get("kind") in {"code", "research", "operations", "audit", "design", "writing"},
            "KIND_INVALID")
    require(c.get("authority") in {"read_only", "branch_only", "operator_required"},
            "AUTHORITY_MISSING")
    require(c.get("risk") in {"low", "moderate", "high"}, "RISK_MISSING")
    scope = c.get("scope")
    require(isinstance(scope, list) and 1 <= len(scope) <= 40 and
            all(isinstance(x, str) and x.strip() and not x.startswith("/") and
                ".." not in x.split("/") and len(x) <= 200 for x in scope), "SCOPE_INVALID")
    forbidden = c.get("forbidden")
    require(isinstance(forbidden, list) and forbidden and
            all(isinstance(s, str) and s.strip() for s in forbidden), "FORBIDDEN_MISSING")
    acceptance = c.get("acceptance")
    require(isinstance(acceptance, list) and 1 <= len(acceptance) <= 30, "ACCEPTANCE_MISSING")
    seen = set()
    for item in acceptance:
        require(isinstance(item, dict) and set(item) >= {"id", "criterion", "method"},
                "ACCEPTANCE_INVALID")
        ident = item["id"]
        require(isinstance(ident, str) and re.fullmatch(r"A[1-9][0-9]*", ident) and ident not in seen,
                "ACCEPTANCE_ID_INVALID_OR_DUPLICATE")
        seen.add(ident)
        require(isinstance(item["criterion"], str) and len(item["criterion"].strip()) >= 10,
                "ACCEPTANCE_CRITERION_VAGUE")
        method = item["method"]
        require(method in {"github_check", "independent_review", "domain_evidence"},
                "ACCEPTANCE_METHOD_UNSUPPORTED")
        if method == "github_check":
            require(isinstance(item.get("check"), str) and item["check"].strip(),
                    "ACCEPTANCE_CHECK_MISSING")
            require(type(item.get("app_id")) is int and item["app_id"] == 15368,
                    "CHECK_PUBLISHER_NOT_TRUSTED")
        else:
            require("check" not in item, "ACCEPTANCE_CHECK_IN_WRONG_METHOD")
    return c


def _check(name, ok, reason=None):
    return {"gate": name, "result": "PASS" if ok else "FAIL", "reason": "OK" if ok else reason}


def assess(snapshot):
    """Pure reducer over a caller-supplied snapshot. Not independent evidence by itself."""
    gates = []
    try:
        require(isinstance(snapshot, dict), "SNAPSHOT_INVALID")
        repo, pr, issue = snapshot["repo"], snapshot["pr"], snapshot["issue"]
        require(isinstance(repo, str) and REPO.fullmatch(repo), "REPO_INVALID")
        require(isinstance(pr, dict) and isinstance(issue, dict), "RECORD_INVALID")
        sha = pr["head"]["sha"]
        require(isinstance(sha, str) and SHA.fullmatch(sha), "HEAD_SHA_INVALID")
        require(type(issue["number"]) is int and issue["number"] > 0, "ISSUE_ID_INVALID")
        c = contract_from_body(issue.get("body"))
        linked = ISSUE_LINK.findall(pr.get("body") or "")
        gates.append(_check("issue_binding", len(linked) == 1 and int(linked[0]) == issue["number"],
                            "PR_ISSUE_LINK_MISSING_OR_CONFLICTING"))
        gates.append(_check("base_branch", pr.get("base", {}).get("ref") == "main",
                            "STACKED_OR_NON_MAIN_BASE"))
        gates.append(_check("issue_open", issue.get("state") == "open"
                            and "pull_request" not in issue, "ISSUE_NOT_OPEN_OR_IS_PR"))
        scope = c["scope"]
        filenames = snapshot.get("changed_files")
        scope_ok = isinstance(filenames, list) and len(filenames) > 0 and all(
            isinstance(f, str) and any(fnmatch.fnmatchcase(f, pattern) for pattern in scope)
            for f in filenames)
        gates.append(_check("declared_scope", scope_ok, "UNBOUND_OR_OUT_OF_SCOPE_DIFF"))
        checks = snapshot.get("check_runs")
        complete = isinstance(checks, list) and snapshot.get("checks_complete") is True
        if not complete:
            gates.append(_check("check_snapshot", False, "CHECKS_MISSING_OR_PAGINATED"))
        for a in c["acceptance"]:
            if a["method"] != "github_check":
                gates.append(_check("acceptance:" + a["id"], False,
                                    "DOMAIN_OR_REVIEW_EVIDENCE_NEEDS_INDEPENDENT_ADAPTER"))
                continue
            name = a["check"]
            matching = [r for r in checks or [] if isinstance(r, dict)
                        and r.get("name") == name and r.get("head_sha") == sha
                        and (r.get("app") or {}).get("id") == a["app_id"]]
            ok = complete and len(matching) == 1 and matching[0].get("status") == "completed" \
                 and matching[0].get("conclusion") == "success"
            gates.append(_check("acceptance:" + a["id"], ok,
                                "NO_SINGLE_SUCCESSFUL_EXACT_HEAD_CHECK"))
        commits = snapshot.get("commits")
        commits_ok = isinstance(commits, list) and len(commits) > 0 and \
            snapshot.get("commits_complete") is True and commits[-1].get("sha") == sha and all(
                isinstance(x, dict) and isinstance(x.get("sha"), str) and SHA.fullmatch(x["sha"])
                and x.get("commit", {}).get("verification", {}).get("verified") is True
                for x in commits)
        gates.append(_check("signed_commits", commits_ok,
                            "UNSIGNED_OR_INCOMPLETE_COMMIT_CHAIN"))
        author = pr.get("user", {}).get("login")
        reviews = snapshot.get("reviews")
        latest = {}
        if isinstance(reviews, list) and snapshot.get("reviews_complete") is True:
            for r in reviews:
                if not isinstance(r, dict) or not isinstance(r.get("user"), dict):
                    continue
                who = r["user"].get("login")
                if not isinstance(who, str) or not who or r.get("state") not in APPROVAL_STATES:
                    continue
                latest[who] = r
        review_ok = any(who != author and r.get("state") == "APPROVED" and
                        r.get("commit_id") == sha for who, r in latest.items())
        gates.append(_check("independent_identity_review", review_ok,
                            "NO_APPROVAL_FROM_DIFFERENT_GITHUB_LOGIN_AT_EXACT_HEAD"))
        gates.append(_check("human_authority_boundary",
                            c["authority"] != "operator_required" and c["risk"] != "high",
                            "CONSEQUENTIAL_OR_HIGH_RISK_ACTION_REQUIRES_OPERATOR"))
        gates.append(_check("non_draft", pr.get("draft") is False, "PR_IS_DRAFT"))
        ok = all(x["result"] == "PASS" for x in gates)
        return {"schema": "aegis.issue-gate.report.v1", "repo": repo,
                "issue": issue["number"], "pr": pr.get("number"), "head_sha": sha,
                "contract": "VALID", "gates": gates,
                "disposition": "EVIDENCE_COMPLETE_NOT_ADMITTED" if ok else "NOT_ADMITTED",
                "authority_effect": "NONE", "source": snapshot.get("source", "caller_supplied_UNTRUSTED")}
    except (Invalid, KeyError, TypeError, ValueError) as exc:
        return {"schema": "aegis.issue-gate.report.v1", "contract": "INVALID",
                "gates": gates, "disposition": "NOT_ADMITTED",
                "authority_effect": "NONE", "reason": str(exc),
                "source": snapshot.get("source", "caller_supplied_UNTRUSTED") if isinstance(snapshot, dict) else "UNKNOWN"}


def _api(repo, route, token):
    url = f"https://api.github.com/repos/{repo}/{route}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AEGIS-issue-gate/1",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers), timeout=15) as response:
        return json.load(response)


def live_snapshot(repo, number, token):
    require(REPO.fullmatch(repo) is not None and type(number) is int and number > 0,
            "REPO_OR_PR_INVALID")
    pr = _api(repo, f"pulls/{number}", token)
    require(pr.get("head", {}).get("repo", {}).get("full_name") == repo,
            "CROSS_REPO_HEAD_UNSUPPORTED")
    sha = pr["head"]["sha"]
    require(SHA.fullmatch(sha) is not None, "HEAD_SHA_INVALID")
    links = ISSUE_LINK.findall(pr.get("body") or "")
    require(len(links) == 1, "MISSING_UNIQUE_LINK")
    issue = _api(repo, f"issues/{int(links[0])}", token)
    data = _api(repo, f"commits/{sha}/check-runs?per_page=100&filter=latest", token)
    reviews = _api(repo, f"pulls/{number}/reviews?per_page=100", token)
    commits = _api(repo, f"pulls/{number}/commits?per_page=100", token)
    files = _api(repo, f"pulls/{number}/files?per_page=100", token)
    return {"source": "github_api_live_read_only", "repo": repo, "pr": pr, "issue": issue,
            "check_runs": data.get("check_runs", []),
            "checks_complete": data.get("total_count") == len(data.get("check_runs", [])),
            "reviews": reviews, "reviews_complete": isinstance(reviews, list) and len(reviews) < 100,
            "commits": commits, "commits_complete": isinstance(commits, list) and len(commits) < 100,
            "changed_files": [f.get("filename") for f in files] if isinstance(files, list) and len(files) < 100 else [],
            "files_complete": isinstance(files, list) and len(files) < 100}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--snapshot", help="Offline fixture JSON (not trusted evidence)")
    src.add_argument("--live-pr", type=int, help="Read-only live GitHub audit")
    p.add_argument("--repo", default="Aegis-Omega/AEGIS-OMEGA")
    p.add_argument("--output", help="Write JSON report to a file")
    args = p.parse_args(argv)
    try:
        if args.snapshot:
            with open(args.snapshot, encoding="utf-8") as f:
                snap = json.load(f)
        else:
            snap = live_snapshot(args.repo, args.live_pr, os.environ.get("GITHUB_TOKEN", ""))
        result = assess(snap)
    except (Invalid, OSError, HTTPError, URLError, ValueError, TypeError, KeyError) as exc:
        result = {"schema": "aegis.issue-gate.report.v1", "disposition": "NOT_ADMITTED",
                  "contract": "UNKNOWN", "authority_effect": "NONE", "reason": type(exc).__name__}
    out = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    print(out, end="")
    return 0 if result["disposition"] == "EVIDENCE_COMPLETE_NOT_ADMITTED" else 1


if __name__ == "__main__":
    sys.exit(main())
