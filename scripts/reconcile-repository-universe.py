#!/usr/bin/env python3
"""Build a deterministic, fail-closed reconciliation census.

This composes the existing Git reachability census (AEGIS_REPO_UNIVERSE_V1)
with an explicit GitHub pull-request census.  It does not classify, merge,
delete, admit, or authorize anything.  Its only authority is discovery
evidence.

The important distinction is structural:

    canonical main          = admitted runtime anchor
    repository/PR universe  = searchable knowledge evidence

A complete discovery pass is still not deletion authority.  Incomplete
sources explicitly deny both deletion and global absence claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "AEGIS_RECONCILIATION_UNIVERSE_V1"
SOURCE_REPO_SCHEMA = "AEGIS_REPO_UNIVERSE_V1"
SOURCE_PR_SCHEMA = "AEGIS_GITHUB_PR_CENSUS_V1"
DIGEST_DOMAIN = b"AEGIS_RECONCILIATION_UNIVERSE_V1\0"
HEX_RE = re.compile(r"^[0-9a-f]{40,64}$")


class ReconciliationCensusError(ValueError):
    """Stable fail-closed input/contract error."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReconciliationCensusError(f"INVALID_JSON:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise ReconciliationCensusError(f"ROOT_NOT_OBJECT:{path}")
    return value


def require_str(obj: Mapping[str, Any], key: str, *, nonempty: bool = True) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise ReconciliationCensusError(f"INVALID_STRING:{key}")
    return value


def require_int(obj: Mapping[str, Any], key: str) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReconciliationCensusError(f"INVALID_INTEGER:{key}")
    return value


def require_bool(obj: Mapping[str, Any], key: str) -> bool:
    value = obj.get(key)
    if not isinstance(value, bool):
        raise ReconciliationCensusError(f"INVALID_BOOLEAN:{key}")
    return value


def require_sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not HEX_RE.fullmatch(value):
        raise ReconciliationCensusError(f"INVALID_SHA:{field}")
    return value


def validate_repo_universe(raw: Mapping[str, Any]) -> None:
    if raw.get("schema_version") != SOURCE_REPO_SCHEMA:
        raise ReconciliationCensusError("UNSUPPORTED_REPO_UNIVERSE_SCHEMA")
    require_sha(raw.get("main_sha"), "main_sha")
    require_str(raw, "main_ref")
    require_bool(raw, "history_complete")
    for key in (
        "branch_count",
        "all_ref_commit_count",
        "main_reachable_commit_count",
        "commits_not_reachable_from_main",
    ):
        require_int(raw, key)
    branches = raw.get("branches")
    if not isinstance(branches, list):
        raise ReconciliationCensusError("BRANCHES_NOT_LIST")
    if raw["branch_count"] != len(branches):
        raise ReconciliationCensusError("BRANCH_COUNT_MISMATCH")
    for index, branch in enumerate(branches):
        if not isinstance(branch, dict):
            raise ReconciliationCensusError(f"BRANCH_NOT_OBJECT:{index}")
        require_str(branch, "branch")
        require_str(branch, "ref")
        require_sha(branch.get("tip"), f"branches[{index}].tip")
        require_int(branch, "ahead_of_main")
        require_int(branch, "behind_main")
        require_bool(branch, "contained_in_main")


def validate_pr_census(raw: Mapping[str, Any]) -> None:
    if raw.get("schema_version") != SOURCE_PR_SCHEMA:
        raise ReconciliationCensusError("UNSUPPORTED_PR_CENSUS_SCHEMA")
    require_str(raw, "repository")
    require_bool(raw, "complete")
    prs = raw.get("pull_requests")
    if not isinstance(prs, list):
        raise ReconciliationCensusError("PULL_REQUESTS_NOT_LIST")
    seen: set[int] = set()
    for index, pr in enumerate(prs):
        if not isinstance(pr, dict):
            raise ReconciliationCensusError(f"PR_NOT_OBJECT:{index}")
        number = pr.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ReconciliationCensusError(f"INVALID_PR_NUMBER:{index}")
        if number in seen:
            raise ReconciliationCensusError(f"DUPLICATE_PR_NUMBER:{number}")
        seen.add(number)
        for key in ("state", "title", "baseRefName", "headRefName", "mergeable", "url"):
            require_str(pr, key)
        require_sha(pr.get("baseRefOid"), f"pull_requests[{number}].baseRefOid")
        require_sha(pr.get("headRefOid"), f"pull_requests[{number}].headRefOid")
        if not isinstance(pr.get("isDraft"), bool):
            raise ReconciliationCensusError(f"INVALID_PR_DRAFT:{number}")


def normalize_prs(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for pr in raw["pull_requests"]:
        assert isinstance(pr, dict)
        result.append(
            {
                "number": pr["number"],
                "state": str(pr["state"]).upper(),
                "draft": bool(pr["isDraft"]),
                "title": pr["title"],
                "base_ref": pr["baseRefName"],
                "base_sha": pr["baseRefOid"],
                "head_ref": pr["headRefName"],
                "head_sha": pr["headRefOid"],
                "mergeable": str(pr["mergeable"]).upper(),
                "url": pr["url"],
            }
        )
    result.sort(key=lambda item: item["number"])
    return result


def normalize_branches(
    raw: Mapping[str, Any], prs: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_head_name: dict[str, list[int]] = {}
    by_head_sha: dict[str, list[int]] = {}
    for pr in prs:
        by_head_name.setdefault(str(pr["head_ref"]), []).append(int(pr["number"]))
        by_head_sha.setdefault(str(pr["head_sha"]), []).append(int(pr["number"]))

    result: list[dict[str, Any]] = []
    for branch in raw["branches"]:
        assert isinstance(branch, dict)
        # Exact object identity (tip SHA) is strongest.  Name linkage is retained as
        # metadata because a PR head ref may still be useful after history changes,
        # but neither relationship is promoted to implementation truth.
        linked = set(by_head_sha.get(str(branch["tip"]), []))
        linked.update(by_head_name.get(str(branch["branch"]), []))
        result.append(
            {
                "branch": branch["branch"],
                "ref": branch["ref"],
                "tip": branch["tip"],
                "ahead_of_main": branch["ahead_of_main"],
                "behind_main": branch["behind_main"],
                "contained_in_main": branch["contained_in_main"],
                "pr_numbers": sorted(linked),
            }
        )
    result.sort(key=lambda item: (str(item["branch"]), str(item["tip"])))
    return result


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def build_reconciliation_universe(
    repo_universe: Mapping[str, Any], pr_census: Mapping[str, Any]
) -> dict[str, Any]:
    validate_repo_universe(repo_universe)
    validate_pr_census(pr_census)

    prs = normalize_prs(pr_census)
    branches = normalize_branches(repo_universe, prs)

    history_complete = bool(repo_universe["history_complete"])
    prs_complete = bool(pr_census["complete"])
    incomplete_sources: list[str] = []
    if not history_complete:
        incomplete_sources.append("git_history")
    if not prs_complete:
        incomplete_sources.append("pull_requests")
    discovery_complete = not incomplete_sources

    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "authority": "DISCOVERY_EVIDENCE_ONLY",
        "repository": pr_census["repository"],
        "canonical_main": {
            "ref": repo_universe["main_ref"],
            "sha": repo_universe["main_sha"],
            "authority": "ADMITTED_RUNTIME_ANCHOR",
        },
        "knowledge_universe": {
            "history_complete": history_complete,
            "branch_count": len(branches),
            "all_ref_commit_count": repo_universe["all_ref_commit_count"],
            "main_reachable_commit_count": repo_universe["main_reachable_commit_count"],
            "commits_not_reachable_from_main": repo_universe["commits_not_reachable_from_main"],
        },
        "pull_request_census_complete": prs_complete,
        "discovery_complete": discovery_complete,
        "incomplete_sources": incomplete_sources,
        # Discovery alone never authorizes destructive cleanup or a universal
        # non-existence statement.  Later classification is mandatory even when
        # both sources are complete.
        "deletion_authority": "CLASSIFICATION_REQUIRED" if discovery_complete else "DENIED",
        "global_absence_claim_authority": "SCOPED_ONLY" if discovery_complete else "DENIED",
        "branches": branches,
        "pull_requests": prs,
        "epistemic_rules": [
            "MAIN_IS_ADMITTED_STATE_NOT_KNOWLEDGE_UNIVERSE",
            "WORKTREE_MISS_IS_NOT_GLOBAL_ABSENCE",
            "BRANCH_OR_PR_NAME_IS_REFERENCE_EVIDENCE_NOT_IMPLEMENTATION_TRUTH",
            "DISCOVERY_COMPLETENESS_IS_NOT_DELETION_AUTHORITY",
        ],
    }
    digest = hashlib.sha256(DIGEST_DOMAIN + canonical_bytes(body)).hexdigest()
    return {**body, "manifest_sha256": digest}


def validate_document(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise ReconciliationCensusError("OUTPUT_SCHEMA_MISMATCH")
    digest = doc.get("manifest_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ReconciliationCensusError("OUTPUT_DIGEST_INVALID")
    body = dict(doc)
    body.pop("manifest_sha256", None)
    expected = hashlib.sha256(DIGEST_DOMAIN + canonical_bytes(body)).hexdigest()
    if digest != expected:
        raise ReconciliationCensusError("OUTPUT_DIGEST_MISMATCH")

    branches = doc.get("branches")
    prs = doc.get("pull_requests")
    if not isinstance(branches, list) or not isinstance(prs, list):
        raise ReconciliationCensusError("OUTPUT_COLLECTION_TYPE_INVALID")
    if branches != sorted(branches, key=lambda item: (str(item["branch"]), str(item["tip"]))):
        raise ReconciliationCensusError("OUTPUT_BRANCH_ORDER_NONDETERMINISTIC")
    if prs != sorted(prs, key=lambda item: int(item["number"])):
        raise ReconciliationCensusError("OUTPUT_PR_ORDER_NONDETERMINISTIC")


def write_document(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-universe", required=True, type=Path)
    parser.add_argument("--prs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        repo_universe = load_json(args.repo_universe)
        pr_census = load_json(args.prs)
        doc = build_reconciliation_universe(repo_universe, pr_census)
        validate_document(doc)
        write_document(args.out, doc)
    except ReconciliationCensusError as exc:
        print(f"reconciliation-census: FAIL_CLOSED {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "schema_version": doc["schema_version"],
                "discovery_complete": doc["discovery_complete"],
                "branch_count": len(doc["branches"]),
                "pr_count": len(doc["pull_requests"]),
                "main_sha": doc["canonical_main"]["sha"],
                "manifest_sha256": doc["manifest_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
