#!/usr/bin/env python3
"""AEGIS #737: read-only PR triage, evidence-first; no PR state mutations.

Inputs: gh pr list --json number,title,headRefName,headRefOid,baseRefName,updatedAt
        plus a date YYYY-MM-DD. All referenced commits must exist locally.
Output: TSV with KEEP, REVIEW or CANDIDATE_CLOSE. Never outputs a command to close.

Guarantee: missing Git objects, failed Git calls, stale dates, research/proof
category, or stacked PRs are NEVER sufficient to recommend closure.

This corrects the 2026-11-02 triage candidate from PR #509, NOT the
current protected main tree. No paid, network, credential or write operations.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

_HEX = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_LANES = ("proof", "research", "evidence")


class SourceUnavailable(Exception):
    pass


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, check=False)
    if r.returncode != 0:
        raise SourceUnavailable("GIT_" + args[0].upper().replace("-", "_") + "_FAILED")
    return r.stdout.strip()


def days_since(value: str, today: dt.date) -> int | None:
    try:
        updated = dt.date.fromisoformat(value[:10])
        gap = (today - updated).days
        return gap if gap >= 0 else None
    except (ValueError, TypeError, IndexError):
        return None


def valid_sha(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX.fullmatch(value))


def classify(pr: dict, *, main_sha: str, today: dt.date) -> tuple[str, str]:
    """Never infer no changes from missing history or a failed Git command."""
    if pr.get("number") == 698:
        return "KEEP", "OPERATOR_PRESERVE_698"
    sha = pr.get("headRefOid")
    base = pr.get("baseRefName")
    head = pr.get("headRefName")
    age = days_since(pr.get("updatedAt"), today)
    if not valid_sha(sha) or not isinstance(base, str) or not isinstance(head, str):
        return "REVIEW", "INVALID_PR_METADATA"
    if age is None:
        return "REVIEW", "INVALID_OR_FUTURE_UPDATED_DATE"
    if base != "main":
        return "REVIEW", "STACKED_DEPENDENCY_REQUIRES_SEMANTIC_REVIEW"
    if head.split("/", 1)[0] in _LANES:
        return "REVIEW", "RESEARCH_PROOF_PRESERVATION_REVIEW"
    try:
        # Distinguish genuinely integrated ancestry from a missing object.
        git("cat-file", "-e", sha + "^{commit}")
        if subprocess.run(["git", "merge-base", "--is-ancestor", sha, main_sha],
                          capture_output=True).returncode == 0:
            return "CANDIDATE_CLOSE", "HEAD_COMMIT_CONTAINED_IN_MAIN"
        # A 1 means non-ancestor, while any other return code is an error.
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", sha, main_sha],
                                  capture_output=True)
        if ancestor.returncode != 1:
            return "REVIEW", "ANCESTRY_UNVERIFIABLE"
        merge_base = git("merge-base", sha, main_sha)
        if not valid_sha(merge_base):
            return "REVIEW", "MERGE_BASE_INVALID"
        names = git("diff", "--name-only", merge_base, sha).splitlines()
        if not names:
            return "CANDIDATE_CLOSE", "EXACT_TREE_DIFF_EMPTY"
        for path in names:
            if not path or "\n" in path:
                return "REVIEW", "DIFF_PATH_UNVERIFIABLE"
            obj = []
            for commit in (sha, main_sha):
                r = subprocess.run(["git", "rev-parse", "--verify", f"{commit}:{path}"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, check=False)
                obj.append(r.stdout.strip() if r.returncode == 0 else None)
            # A failed read is not proof of identical content, including both missing.
            if obj[0] is None or obj[1] is None or obj[0] != obj[1]:
                return "REVIEW", "UNINTEGRATED_OR_UNRESOLVED_FILE_BYTES"
        return "CANDIDATE_CLOSE", "ALL_CHANGED_FILE_BLOBS_EQUAL_MAIN"
    except (SourceUnavailable, OSError) as e:
        return "REVIEW", "GIT_EVIDENCE_UNAVAILABLE"


def render(prs: object, today: dt.date) -> str:
    if not isinstance(prs, list):
        raise ValueError("PR_LIST_REQUIRED")
    main_sha = git("rev-parse", "--verify", "origin/main^{commit}")
    if not valid_sha(main_sha):
        raise SourceUnavailable("MAIN_SHA_INVALID")
    rows = []
    seen_ids, seen_refs = set(), set()
    for p in prs:
        if not isinstance(p, dict) or type(p.get("number")) is not int:
            raise ValueError("INVALID_PR_ITEM")
        if p["number"] in seen_ids or p.get("headRefName") in seen_refs:
            raise ValueError("DUPLICATE_PR_ID_OR_HEAD")
        seen_ids.add(p["number"])
        seen_refs.add(p.get("headRefName"))
        verdict, reason = classify(p, main_sha=main_sha, today=today)
        cols = [p["number"], verdict, reason, p.get("headRefName", "UNKNOWN"),
                p.get("baseRefName", "UNKNOWN"), str(p.get("updatedAt", ""))[:10]]
        rows.append("\t".join(map(str, cols)))
    return "pr\tverdict\treason\thead\tbase\tupdated\n" + "\n".join(sorted(rows, key=lambda x: int(x.split("\t", 1)[0]))) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: pr_triage_safe.py open_prs.json YYYY-MM-DD", file=sys.stderr)
        return 2
    try:
        today = dt.date.fromisoformat(args[1])
        path = Path(args[0])
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4_000_000:
            raise ValueError("SOURCE_FILE_UNAVAILABLE_OR_TOO_LARGE")
        prs = json.loads(path.read_text(encoding="utf-8"))
        sys.stdout.write(render(prs, today))
        return 0
    except (ValueError, OSError, SourceUnavailable, json.JSONDecodeError) as exc:
        print(f"TRIAGE_ABORT: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
