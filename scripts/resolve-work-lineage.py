#!/usr/bin/env python3
"""Resolve an AEGIS work request against the existing WorkID lineage graph.

The resolver is deterministic and evidence-bound.  It is deliberately NOT a
semantic similarity engine.  A model/embedding score, branch-name resemblance,
or provider suggestion cannot authorize a new branch.

Only these evidence classes participate in compatibility v1:
  * exact objective digest;
  * exact referenced artifact overlap;
  * capability overlap AND path overlap;
  * explicit parent WorkIDs (for STACK_ON_EXISTING).

A new branch is authorized iff the result is CREATE_NEW and discovery is
complete.  Every other result denies branch creation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

LINEAGE_SCHEMA = "AEGIS_WORK_LINEAGE_V1"
REQUEST_SCHEMA = "AEGIS_WORK_REQUEST_V1"
OUTPUT_SCHEMA = "AEGIS_WORK_LINEAGE_RESOLUTION_V1"
REQUEST_DOMAIN = b"AEGIS_WORK_REQUEST_V1\0"
RESOLUTION_DOMAIN = b"AEGIS_WORK_LINEAGE_RESOLUTION_V1\0"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40_64 = re.compile(r"^[0-9a-f]{40,64}$")
WORK_ID_RE = re.compile(r"^(?:pr:[1-9][0-9]*|legacy-tip:[0-9a-f]{64})$")
RESOLUTIONS = {
    "CONTINUE_EXISTING",
    "STACK_ON_EXISTING",
    "RESUME_ABANDONED",
    "CREATE_NEW",
    "AMBIGUOUS_HALT",
}


class LineageResolutionError(ValueError):
    pass


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LineageResolutionError(f"INVALID_JSON:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise LineageResolutionError(f"ROOT_NOT_OBJECT:{path}")
    return value


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def hash_document(domain: bytes, value: Mapping[str, Any]) -> str:
    return hashlib.sha256(domain + canonical_bytes(value)).hexdigest()


def require_string_list(obj: Mapping[str, Any], key: str) -> list[str]:
    value = obj.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise LineageResolutionError(f"INVALID_STRING_LIST:{key}")
    if len(value) != len(set(value)):
        raise LineageResolutionError(f"DUPLICATE_STRING_LIST:{key}")
    return list(value)


def optional_string_list(obj: Mapping[str, Any], key: str) -> list[str]:
    value = obj.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise LineageResolutionError(f"INVALID_OPTIONAL_STRING_LIST:{key}")
    return list(dict.fromkeys(value))


def validate_lineage(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != LINEAGE_SCHEMA:
        raise LineageResolutionError("UNSUPPORTED_LINEAGE_SCHEMA")
    if doc.get("authority") != "LINEAGE_DISCOVERY_EVIDENCE_ONLY":
        raise LineageResolutionError("LINEAGE_AUTHORITY_UNSUPPORTED")
    if not isinstance(doc.get("discovery_complete"), bool):
        raise LineageResolutionError("LINEAGE_COMPLETENESS_INVALID")
    items = doc.get("work_items")
    if not isinstance(items, list):
        raise LineageResolutionError("WORK_ITEMS_NOT_LIST")
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise LineageResolutionError(f"WORK_ITEM_NOT_OBJECT:{index}")
        work_id = item.get("work_id")
        if not isinstance(work_id, str) or not WORK_ID_RE.fullmatch(work_id):
            raise LineageResolutionError(f"WORK_ID_INVALID:{index}")
        if work_id in seen:
            raise LineageResolutionError(f"WORK_ID_DUPLICATE:{work_id}")
        seen.add(work_id)
        head = item.get("current_head")
        if not isinstance(head, str) or not HEX40_64.fullmatch(head):
            raise LineageResolutionError(f"WORK_HEAD_INVALID:{work_id}")
        ref = item.get("current_ref")
        if not isinstance(ref, str) or not ref:
            raise LineageResolutionError(f"WORK_REF_INVALID:{work_id}")
        objective = item.get("objective_digest")
        if objective is not None and (not isinstance(objective, str) or not HEX64.fullmatch(objective)):
            raise LineageResolutionError(f"WORK_OBJECTIVE_DIGEST_INVALID:{work_id}")
        superseded = item.get("superseded_by")
        if superseded is not None and (not isinstance(superseded, str) or not WORK_ID_RE.fullmatch(superseded)):
            raise LineageResolutionError(f"WORK_SUPERSESSION_INVALID:{work_id}")


def validate_request(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != REQUEST_SCHEMA:
        raise LineageResolutionError("UNSUPPORTED_REQUEST_SCHEMA")
    objective = doc.get("objective_digest")
    if not isinstance(objective, str) or not HEX64.fullmatch(objective):
        raise LineageResolutionError("REQUEST_OBJECTIVE_DIGEST_INVALID")
    for key in ("capability_set", "paths", "explicit_parent_work_ids", "referenced_artifacts"):
        require_string_list(doc, key)
    for work_id in doc["explicit_parent_work_ids"]:
        if not WORK_ID_RE.fullmatch(work_id):
            raise LineageResolutionError(f"REQUEST_PARENT_WORK_ID_INVALID:{work_id}")
    hint = doc.get("branch_name_hint")
    if hint is not None and (not isinstance(hint, str) or not hint.strip()):
        raise LineageResolutionError("REQUEST_BRANCH_HINT_INVALID")


def is_active(item: Mapping[str, Any]) -> bool:
    state = str(item.get("state", "")).upper()
    classification = str(item.get("classification", ""))
    return state in {"OPEN", "REACHABLE_REF"} and classification not in {
        "HISTORICAL_EVIDENCE_ONLY",
        "SUPERSEDED_BY",
        "REDUNDANT_PROVEN",
    }


def is_resumable(item: Mapping[str, Any]) -> bool:
    state = str(item.get("state", "")).upper()
    if item.get("superseded_by") is not None:
        return False
    return state in {"CLOSED", "ABANDONED", "STALE", "RECOVERY_REQUIRED"}


def set_overlap(left: Iterable[str], right: Iterable[str]) -> list[str]:
    return sorted(set(left).intersection(right))


def compatibility(item: Mapping[str, Any], request: Mapping[str, Any]) -> tuple[int, list[str]]:
    """Return an ordinal evidence score and its exact basis.

    Score is only a deterministic tie/priority mechanism over explicit evidence;
    it is not a probability or semantic similarity value.
    """
    if item.get("superseded_by") is not None:
        return 0, []

    basis: list[str] = []
    score = 0
    if item.get("objective_digest") == request.get("objective_digest"):
        basis.append("EXACT_OBJECTIVE_DIGEST")
        score += 100

    request_artifacts = require_string_list(request, "referenced_artifacts")
    item_artifacts = optional_string_list(item, "artifact_refs")
    artifact_overlap = set_overlap(request_artifacts, item_artifacts)
    if artifact_overlap:
        basis.append("EXACT_ARTIFACT_REF")
        score += 80

    request_caps = require_string_list(request, "capability_set")
    request_paths = require_string_list(request, "paths")
    item_caps = optional_string_list(item, "capability_set")
    item_paths = optional_string_list(item, "path_evidence")
    cap_overlap = set_overlap(request_caps, item_caps)
    path_overlap = set_overlap(request_paths, item_paths)
    if cap_overlap and path_overlap:
        basis.append("CAPABILITY_AND_PATH_OVERLAP")
        score += 60

    # branch_name_hint is intentionally ignored.  A branch/ref label is mutable
    # transport metadata and cannot establish compatible work identity.
    return score, basis


def item_by_id(lineage: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item["work_id"]): item for item in lineage["work_items"]}


def make_result(
    *,
    lineage: Mapping[str, Any],
    request: Mapping[str, Any],
    resolution: str,
    work_id: str | None,
    continuation_ref: str | None,
    expected_head: str | None,
    parent_work_ids: Sequence[str],
    candidate_work_ids: Sequence[str],
    evidence_basis: Sequence[str],
) -> dict[str, Any]:
    if resolution not in RESOLUTIONS:
        raise LineageResolutionError("INTERNAL_RESOLUTION_INVALID")
    discovery_complete = bool(lineage["discovery_complete"])
    branch_creation_allowed = resolution == "CREATE_NEW" and discovery_complete
    body: dict[str, Any] = {
        "schema_version": OUTPUT_SCHEMA,
        "authority": "ROUTING_EVIDENCE_ONLY",
        "resolution": resolution,
        "work_id": work_id,
        "continuation_ref": continuation_ref,
        "expected_head": expected_head,
        "parent_work_ids": list(parent_work_ids),
        "candidate_work_ids": sorted(set(candidate_work_ids)),
        "evidence_basis": sorted(set(evidence_basis)),
        "discovery_complete": discovery_complete,
        "branch_creation_allowed": branch_creation_allowed,
        "source_lineage_manifest_sha256": lineage.get("manifest_sha256"),
        "request_digest": hash_document(REQUEST_DOMAIN, request),
        "rules": [
            "BRANCH_NAME_IS_NOT_WORK_IDENTITY",
            "CREATE_NEW_REQUIRES_COMPLETE_DISCOVERY",
            "COMPATIBLE_EXISTING_WORK_DENIES_BRANCH_CREATION",
            "AMBIGUITY_FAILS_CLOSED",
        ],
    }
    return {**body, "resolution_digest": hash_document(RESOLUTION_DOMAIN, body)}


def resolve(lineage: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    validate_lineage(lineage)
    validate_request(request)
    by_id = item_by_id(lineage)

    explicit_parents = require_string_list(request, "explicit_parent_work_ids")
    missing_parents = sorted(work_id for work_id in explicit_parents if work_id not in by_id)
    if missing_parents:
        return make_result(
            lineage=lineage,
            request=request,
            resolution="AMBIGUOUS_HALT",
            work_id=None,
            continuation_ref=None,
            expected_head=None,
            parent_work_ids=explicit_parents,
            candidate_work_ids=[],
            evidence_basis=["EXPLICIT_PARENT_UNKNOWN", *[f"MISSING:{x}" for x in missing_parents]],
        )

    ranked: list[tuple[int, str, list[str], Mapping[str, Any]]] = []
    for item in lineage["work_items"]:
        score, basis = compatibility(item, request)
        if score > 0:
            ranked.append((score, str(item["work_id"]), basis, item))
    ranked.sort(key=lambda row: (-row[0], row[1]))

    active_ranked = [row for row in ranked if is_active(row[3])]
    if active_ranked:
        top = active_ranked[0][0]
        winners = [row for row in active_ranked if row[0] == top]
        if len(winners) > 1:
            return make_result(
                lineage=lineage,
                request=request,
                resolution="AMBIGUOUS_HALT",
                work_id=None,
                continuation_ref=None,
                expected_head=None,
                parent_work_ids=explicit_parents,
                candidate_work_ids=[row[1] for row in winners],
                evidence_basis=[basis for row in winners for basis in row[2]],
            )
        _, work_id, basis, item = winners[0]
        return make_result(
            lineage=lineage,
            request=request,
            resolution="CONTINUE_EXISTING",
            work_id=work_id,
            continuation_ref=str(item["current_ref"]),
            expected_head=str(item["current_head"]),
            parent_work_ids=list(item.get("parent_work_ids") or []),
            candidate_work_ids=[work_id],
            evidence_basis=basis,
        )

    # An explicit parent request is a stack request when the same objective does
    # not already resolve to active work.  Parent existence was verified above.
    if explicit_parents:
        parent_items = [by_id[work_id] for work_id in explicit_parents]
        continuation_ref = str(parent_items[0]["current_ref"]) if len(parent_items) == 1 else None
        expected_head = str(parent_items[0]["current_head"]) if len(parent_items) == 1 else None
        return make_result(
            lineage=lineage,
            request=request,
            resolution="STACK_ON_EXISTING",
            work_id=None,
            continuation_ref=continuation_ref,
            expected_head=expected_head,
            parent_work_ids=explicit_parents,
            candidate_work_ids=explicit_parents,
            evidence_basis=["EXPLICIT_PARENT_WORK_ID"],
        )

    resumable = [row for row in ranked if is_resumable(row[3])]
    if resumable:
        top = resumable[0][0]
        winners = [row for row in resumable if row[0] == top]
        if len(winners) > 1:
            return make_result(
                lineage=lineage,
                request=request,
                resolution="AMBIGUOUS_HALT",
                work_id=None,
                continuation_ref=None,
                expected_head=None,
                parent_work_ids=[],
                candidate_work_ids=[row[1] for row in winners],
                evidence_basis=[basis for row in winners for basis in row[2]],
            )
        _, work_id, basis, item = winners[0]
        return make_result(
            lineage=lineage,
            request=request,
            resolution="RESUME_ABANDONED",
            work_id=work_id,
            continuation_ref=str(item["current_ref"]),
            expected_head=str(item["current_head"]),
            parent_work_ids=list(item.get("parent_work_ids") or []),
            candidate_work_ids=[work_id],
            evidence_basis=basis,
        )

    # Non-active compatible evidence that is neither resumable nor superseded is
    # not safe to ignore.  It requires a human/reconciliation decision.
    unresolved = [row for row in ranked if row[3].get("superseded_by") is None]
    if unresolved:
        top = unresolved[0][0]
        winners = [row for row in unresolved if row[0] == top]
        return make_result(
            lineage=lineage,
            request=request,
            resolution="AMBIGUOUS_HALT",
            work_id=None,
            continuation_ref=None,
            expected_head=None,
            parent_work_ids=[],
            candidate_work_ids=[row[1] for row in winners],
            evidence_basis=["COMPATIBLE_NONRESUMABLE_WORK", *[basis for row in winners for basis in row[2]]],
        )

    if not lineage["discovery_complete"]:
        return make_result(
            lineage=lineage,
            request=request,
            resolution="AMBIGUOUS_HALT",
            work_id=None,
            continuation_ref=None,
            expected_head=None,
            parent_work_ids=[],
            candidate_work_ids=[],
            evidence_basis=["DISCOVERY_INCOMPLETE"],
        )

    return make_result(
        lineage=lineage,
        request=request,
        resolution="CREATE_NEW",
        work_id=None,
        continuation_ref=None,
        expected_head=None,
        parent_work_ids=[],
        candidate_work_ids=[],
        evidence_basis=["NO_COMPATIBLE_WORK_FOUND_IN_COMPLETE_DISCOVERY"],
    )


def validate_output(doc: Mapping[str, Any]) -> None:
    resolution = doc.get("resolution")
    if resolution not in RESOLUTIONS:
        raise LineageResolutionError("OUTPUT_RESOLUTION_INVALID")
    allowed = doc.get("branch_creation_allowed")
    if not isinstance(allowed, bool):
        raise LineageResolutionError("OUTPUT_BRANCH_GATE_INVALID")
    expected_allowed = resolution == "CREATE_NEW" and doc.get("discovery_complete") is True
    if allowed != expected_allowed:
        raise LineageResolutionError("OUTPUT_BRANCH_GATE_INVARIANT_BROKEN")
    if allowed and doc.get("candidate_work_ids"):
        raise LineageResolutionError("CREATE_NEW_WITH_EXISTING_CANDIDATES")
    body = dict(doc)
    actual = body.pop("resolution_digest", None)
    if actual != hash_document(RESOLUTION_DOMAIN, body):
        raise LineageResolutionError("OUTPUT_DIGEST_MISMATCH")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lineage", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        lineage = load_object(args.lineage)
        request = load_object(args.request)
        result = resolve(lineage, request)
        validate_output(result)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except LineageResolutionError as exc:
        print(f"resolve-work-lineage: FAIL_CLOSED {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "resolution": result["resolution"],
        "work_id": result["work_id"],
        "continuation_ref": result["continuation_ref"],
        "expected_head": result["expected_head"],
        "branch_creation_allowed": result["branch_creation_allowed"],
        "resolution_digest": result["resolution_digest"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
