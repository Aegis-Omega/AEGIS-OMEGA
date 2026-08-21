#!/usr/bin/env python3
"""Collect conservative structural evidence for repository reconciliation.

This collector intentionally does *less* than the classifier needs for a final
merge/delete decision.  It binds current GitHub PR topology to stable WorkIDs,
but it never fabricates exact-head CI verification, unique-capability analysis,
recovery status, or containment proof.

Therefore ``complete`` is always false in v1 and the coverage declaration is
``STRUCTURAL_PR_METADATA_ONLY``.  Later reconciliation phases may enrich this
schema with independently verified evidence before classification is promoted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

LINEAGE_SCHEMA = "AEGIS_WORK_LINEAGE_V1"
PR_SCHEMA = "AEGIS_GITHUB_PR_CENSUS_V1"
OUTPUT_SCHEMA = "AEGIS_RECONCILIATION_EVIDENCE_V1"
DIGEST_DOMAIN = b"AEGIS_RECONCILIATION_EVIDENCE_V1\0"
HEX40_64 = re.compile(r"^[0-9a-f]{40,64}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceCollectionError(ValueError):
    pass


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceCollectionError(f"INVALID_JSON:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceCollectionError(f"ROOT_NOT_OBJECT:{path}")
    return value


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(DIGEST_DOMAIN + canonical_bytes(value)).hexdigest()


def validate_lineage(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != LINEAGE_SCHEMA:
        raise EvidenceCollectionError("UNSUPPORTED_LINEAGE_SCHEMA")
    if doc.get("authority") != "LINEAGE_DISCOVERY_EVIDENCE_ONLY":
        raise EvidenceCollectionError("LINEAGE_AUTHORITY_UNSUPPORTED")
    manifest = doc.get("manifest_sha256")
    if not isinstance(manifest, str) or not HEX64.fullmatch(manifest):
        raise EvidenceCollectionError("LINEAGE_MANIFEST_INVALID")
    if not isinstance(doc.get("work_items"), list):
        raise EvidenceCollectionError("LINEAGE_WORK_ITEMS_INVALID")


def validate_prs(doc: Mapping[str, Any], repository: str) -> None:
    if doc.get("schema_version") != PR_SCHEMA:
        raise EvidenceCollectionError("UNSUPPORTED_PR_CENSUS_SCHEMA")
    if doc.get("repository") != repository:
        raise EvidenceCollectionError("REPOSITORY_BINDING_MISMATCH")
    if not isinstance(doc.get("complete"), bool):
        raise EvidenceCollectionError("PR_CENSUS_COMPLETENESS_INVALID")
    prs = doc.get("pull_requests")
    if not isinstance(prs, list):
        raise EvidenceCollectionError("PULL_REQUESTS_NOT_LIST")
    seen: set[int] = set()
    for pr in prs:
        if not isinstance(pr, dict):
            raise EvidenceCollectionError("PR_NOT_OBJECT")
        number = pr.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise EvidenceCollectionError("PR_NUMBER_INVALID")
        if number in seen:
            raise EvidenceCollectionError(f"PR_NUMBER_DUPLICATE:{number}")
        seen.add(number)
        for key in ("baseRefOid", "headRefOid"):
            value = pr.get(key)
            if not isinstance(value, str) or not HEX40_64.fullmatch(value):
                raise EvidenceCollectionError(f"PR_SHA_INVALID:{number}:{key}")
        if not isinstance(pr.get("mergeable"), str):
            raise EvidenceCollectionError(f"PR_MERGEABLE_INVALID:{number}")


def mergeable_value(raw: str) -> bool | None:
    value = raw.upper()
    if value == "MERGEABLE":
        return True
    if value == "CONFLICTING":
        return False
    return None


def collect(lineage: Mapping[str, Any], prs_doc: Mapping[str, Any]) -> dict[str, Any]:
    validate_lineage(lineage)
    repository = lineage.get("repository")
    if not isinstance(repository, str) or not repository:
        raise EvidenceCollectionError("LINEAGE_REPOSITORY_INVALID")
    validate_prs(prs_doc, repository)

    by_number = {
        int(pr["number"]): pr
        for pr in prs_doc["pull_requests"]
        if isinstance(pr, dict)
    }

    work: dict[str, Any] = {}
    pr_backed_count = 0
    matched_count = 0
    for item in lineage["work_items"]:
        if not isinstance(item, dict):
            raise EvidenceCollectionError("WORK_ITEM_NOT_OBJECT")
        work_id = item.get("work_id")
        if not isinstance(work_id, str) or not work_id:
            raise EvidenceCollectionError("WORK_ID_INVALID")
        pr_number = item.get("pr_number")
        if pr_number is None:
            # Branch-only legacy work has no PR authority surface.  Omitting it is
            # safer than inventing an evidence record from branch metadata.
            continue
        if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number < 1:
            raise EvidenceCollectionError(f"PR_NUMBER_INVALID_FOR_WORK:{work_id}")
        pr_backed_count += 1
        pr = by_number.get(pr_number)
        if pr is None:
            continue
        matched_count += 1

        expected_parent = item.get("base_sha")
        if expected_parent is not None and (
            not isinstance(expected_parent, str) or not HEX40_64.fullmatch(expected_parent)
        ):
            raise EvidenceCollectionError(f"WORK_BASE_SHA_INVALID:{work_id}")

        work[work_id] = {
            "observed_head": pr["headRefOid"],
            "mergeable": mergeable_value(str(pr["mergeable"])),
            "exact_head_verified": False,
            "expected_parent_sha": expected_parent,
            "current_parent_sha": pr["baseRefOid"],
            "blockers": [],
            "verification_roots": [],
            "unique_capability_evidence_roots": [],
            "recovery_required": False,
            "containment_proof": None,
        }

    ordered_work = {key: work[key] for key in sorted(work)}
    body: dict[str, Any] = {
        "schema_version": OUTPUT_SCHEMA,
        "authority": "CLASSIFICATION_EVIDENCE_ONLY",
        # Structural GitHub metadata cannot close verification, recovery,
        # uniqueness or containment. v1 is *always* incomplete by construction.
        "complete": False,
        "coverage": "STRUCTURAL_PR_METADATA_ONLY",
        "repository": repository,
        "source_lineage_manifest_sha256": lineage["manifest_sha256"],
        "source_pr_census_complete": prs_doc["complete"],
        "pr_backed_work_count": pr_backed_count,
        "matched_pr_work_count": matched_count,
        "work": ordered_work,
        "limitations": [
            "CONTAINMENT_NOT_PROVEN",
            "EXACT_HEAD_CI_NOT_COLLECTED",
            "RECOVERY_STATUS_NOT_AUDITED",
            "UNIQUE_CAPABILITY_NOT_AUDITED",
        ],
    }
    return {**body, "manifest_sha256": digest(body)}


def validate_output(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != OUTPUT_SCHEMA:
        raise EvidenceCollectionError("OUTPUT_SCHEMA_INVALID")
    if doc.get("complete") is not False:
        raise EvidenceCollectionError("OUTPUT_MUST_REMAIN_INCOMPLETE_V1")
    if doc.get("coverage") != "STRUCTURAL_PR_METADATA_ONLY":
        raise EvidenceCollectionError("OUTPUT_COVERAGE_INVALID")
    work = doc.get("work")
    if not isinstance(work, dict):
        raise EvidenceCollectionError("OUTPUT_WORK_INVALID")
    if list(work) != sorted(work):
        raise EvidenceCollectionError("OUTPUT_WORK_ORDER_NONDETERMINISTIC")
    body = dict(doc)
    actual = body.pop("manifest_sha256", None)
    if actual != digest(body):
        raise EvidenceCollectionError("OUTPUT_DIGEST_MISMATCH")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lineage", required=True, type=Path)
    parser.add_argument("--prs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        lineage = load_object(args.lineage)
        prs_doc = load_object(args.prs)
        result = collect(lineage, prs_doc)
        validate_output(result)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except EvidenceCollectionError as exc:
        print(f"collect-reconciliation-evidence: FAIL_CLOSED {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "schema_version": result["schema_version"],
        "complete": result["complete"],
        "coverage": result["coverage"],
        "pr_backed_work_count": result["pr_backed_work_count"],
        "matched_pr_work_count": result["matched_pr_work_count"],
        "manifest_sha256": result["manifest_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
