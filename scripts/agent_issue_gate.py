#!/usr/bin/env python3
"""AEGIS issue delivery gate. Read-only, fail-closed, no dynamic code execution.

It checks one PR against a machine-readable GitHub Issue contract and live,
exact-head GitHub evidence. A positive finding means only that enumerated gates
are satisfied; it is NOT branch protection, provenance signing or merge authority.
"""
import argparse
import fnmatch
from functools import lru_cache
import hashlib
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
CONTRACT_LINK = re.compile(r"(?mi)^AEGIS-WORK-CONTRACT-SHA256:\s*([0-9a-f]{64})\s*$")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
APPROVAL_STATES = {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"}


class Invalid(Exception):
    pass


def require(test, reason):
    if not test:
        raise Invalid(reason)


def _unique_object_pairs(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, "CONTRACT_DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def contract_from_body(body):
    require(isinstance(body, str), "ISSUE_BODY_MISSING")
    blocks = MARKER.findall(body)
    require(len(blocks) == 1, "CONTRACT_MARKER_MISSING_OR_DUPLICATED")
    try:
        c = json.loads(blocks[0], object_pairs_hook=_unique_object_pairs)
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


def contract_digest(contract):
    """Stable checksum of the validated contract (integrity, not authorization)."""
    encoded = json.dumps(contract, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def scope_path_matches(path, pattern):
    """Component-aware glob: `*` never crosses `/`; only `**` is recursive."""
    if not (isinstance(path, str) and isinstance(pattern, str)):
        return False
    parts, globs = path.split("/"), pattern.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        return False

    @lru_cache(maxsize=None)
    def match(i, j):
        if j == len(globs):
            return i == len(parts)
        if globs[j] == "**":
            return match(i, j + 1) or (i < len(parts) and match(i + 1, j))
        return i < len(parts) and fnmatch.fnmatchcase(parts[i], globs[j]) and match(i + 1, j + 1)

    return match(0, 0)


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
        digest = contract_digest(c)
        linked = ISSUE_LINK.findall(pr.get("body") or "")
        gates.append(_check("issue_binding", len(linked) == 1 and int(linked[0]) == issue["number"],
                            "PR_ISSUE_LINK_MISSING_OR_CONFLICTING"))
        bound_digests = CONTRACT_LINK.findall(pr.get("body") or "")
        gates.append(_check("contract_binding", bound_digests == [digest],
                            "PR_CONTRACT_DIGEST_MISSING_OR_STALE"))
        gates.append(_check("base_branch", pr.get("base", {}).get("ref") == "main",
                            "STACKED_OR_NON_MAIN_BASE"))
        gates.append(_check("issue_open", issue.get("state") == "open"
                            and "pull_request" not in issue, "ISSUE_NOT_OPEN_OR_IS_PR"))
        scope = c["scope"]
        filenames = snapshot.get("changed_files")
        scope_ok = snapshot.get("files_complete") is True and isinstance(filenames, list) and len(filenames) > 0 and all(
            isinstance(f, str) and any(scope_path_matches(f, pattern) for pattern in scope)
            for f in filenames)
        gates.append(_check("declared_scope", scope_ok, "INCOMPLETE_OR_OUT_OF_SCOPE_DIFF"))
        gates.append(_check("pr_open", pr.get("state") == "open", "PR_NOT_OPEN"))
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
        author_obj = pr.get("user") or {}
        author_login = author_obj.get("login")
        author_id = author_obj.get("id")
        valid_author = (isinstance(author_login, str) and bool(author_login.strip())
                        and type(author_id) is int and author_id > 0)
        reviews = snapshot.get("reviews")
        latest = {}
        valid_reviews = isinstance(reviews, list) and snapshot.get("reviews_complete") is True
        if valid_reviews:
            for r in reviews:
                if not isinstance(r, dict):
                    valid_reviews = False
                    break
                user = r.get("user") or {}
                reviewer_id = user.get("id")
                login = user.get("login")
                review_id = r.get("id")
                if (type(reviewer_id) is not int or reviewer_id < 1 or
                        not isinstance(login, str) or not login.strip() or
                        type(review_id) is not int or review_id < 1):
                    valid_reviews = False
                    break
                if r.get("state") not in APPROVAL_STATES:
                    continue  # GitHub PENDING reviews do not represent a decision.
                previous = latest.get(reviewer_id)
                if previous is None or review_id > previous["id"]:
                    latest[reviewer_id] = r
        review_ok = valid_author and valid_reviews and any(
            reviewer_id != author_id
            and r["user"]["login"].casefold() != author_login.casefold()
            and r.get("state") == "APPROVED" and r.get("commit_id") == sha
            and CONTRACT_LINK.findall(r.get("body") or "") == [digest]
            for reviewer_id, r in latest.items())
        gates.append(_check("independent_identity_review", review_ok,
                            "NO_APPROVAL_FROM_DIFFERENT_GITHUB_LOGIN_AT_EXACT_HEAD"))
        gates.append(_check("human_authority_boundary",
                            c["authority"] != "operator_required" and c["risk"] != "high",
                            "CONSEQUENTIAL_OR_HIGH_RISK_ACTION_REQUIRES_OPERATOR"))
        gates.append(_check("non_draft", pr.get("draft") is False, "PR_IS_DRAFT"))
        ok = all(x["result"] == "PASS" for x in gates)
        return {"schema": "aegis.issue-gate.report.v1", "repo": repo,
                "issue": issue["number"], "pr": pr.get("number"), "head_sha": sha,
                "contract": "VALID", "contract_sha256": digest, "gates": gates,
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
    # Detect a moving PR head, altered acceptance contract or changed approval surface.
    # A read-only API sequence is not an atomic snapshot; fail closed on observable drift.
    latest_pr = _api(repo, f"pulls/{number}", token)
    latest_issue = _api(repo, f"issues/{int(links[0])}", token)
    pr_fields = (("head", "sha"), ("base", "ref"))
    require(all(pr.get(outer, {}).get(inner) == latest_pr.get(outer, {}).get(inner)
                for outer, inner in pr_fields)
            and pr.get("body") == latest_pr.get("body")
            and pr.get("draft") == latest_pr.get("draft")
            and pr.get("state") == latest_pr.get("state"), "PR_CHANGED_DURING_SNAPSHOT")
    require(issue.get("body") == latest_issue.get("body")
            and issue.get("state") == latest_issue.get("state")
            and issue.get("updated_at") == latest_issue.get("updated_at"),
            "ISSUE_CHANGED_DURING_SNAPSHOT")
    return {"source": "github_api_live_read_only", "repo": repo, "pr": latest_pr, "issue": latest_issue,
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
            require(isinstance(snap, dict), "SNAPSHOT_INVALID")
            snap["source"] = "caller_supplied_UNTRUSTED"
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
