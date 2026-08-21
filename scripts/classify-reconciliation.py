#!/usr/bin/env python3
"""Classify AEGIS work and emit a replay-verifiable decision chain.

This layer is evidence-only.  It does not merge, delete, retarget, admit, or
execute work.  It turns a WorkID lineage plus explicit reconciliation evidence
into one closed classification per work item and a deterministic JSONL chain
recording why.

`mergeable=true` is never sufficient for READY_TO_ADMIT.  Exact current-head
verification, unchanged parent binding, non-draft state, complete discovery,
and absence of blockers are all required.
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
EVIDENCE_SCHEMA = "AEGIS_RECONCILIATION_EVIDENCE_V1"
OUTPUT_SCHEMA = "AEGIS_RECONCILIATION_CLASSIFICATION_V1"
DECISION_SCHEMA = "AEGIS_RECONCILIATION_DECISION_V1"
OUTPUT_DOMAIN = b"AEGIS_RECONCILIATION_CLASSIFICATION_V1\0"
EVIDENCE_DOMAIN = b"AEGIS_RECONCILIATION_EVIDENCE_V1\0"
DECISION_DOMAIN = b"AEGIS_RECONCILIATION_DECISION_V1\0"
HEX40_64 = re.compile(r"^[0-9a-f]{40,64}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

CLASSIFICATIONS = {
    "ACTIVE_SPINE",
    "READY_TO_ADMIT",
    "NEEDS_REVERIFY",
    "BLOCKED",
    "UNIQUE_SIDE_CAPABILITY",
    "SUPERSEDED_BY",
    "REDUNDANT_PROVEN",
    "HISTORICAL_EVIDENCE_ONLY",
    "RECOVERY_REQUIRED",
    "UNKNOWN_FAIL_CLOSED",
}


class ClassificationError(ValueError):
    pass


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClassificationError(f"INVALID_JSON:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise ClassificationError(f"ROOT_NOT_OBJECT:{path}")
    return value


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hash_doc(domain: bytes, value: Mapping[str, Any]) -> str:
    return hashlib.sha256(domain + canonical_bytes(value)).hexdigest()


def string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
        raise ClassificationError(f"INVALID_STRING_LIST:{field}")
    if len(value) != len(set(value)):
        raise ClassificationError(f"DUPLICATE_STRING_LIST:{field}")
    return list(value)


def validate_lineage(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != LINEAGE_SCHEMA:
        raise ClassificationError("UNSUPPORTED_LINEAGE_SCHEMA")
    if doc.get("authority") != "LINEAGE_DISCOVERY_EVIDENCE_ONLY":
        raise ClassificationError("LINEAGE_AUTHORITY_UNSUPPORTED")
    if not isinstance(doc.get("discovery_complete"), bool):
        raise ClassificationError("LINEAGE_COMPLETENESS_INVALID")
    manifest = doc.get("manifest_sha256")
    if not isinstance(manifest, str) or not HEX64.fullmatch(manifest):
        raise ClassificationError("LINEAGE_MANIFEST_INVALID")
    items = doc.get("work_items")
    if not isinstance(items, list):
        raise ClassificationError("WORK_ITEMS_NOT_LIST")
    ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ClassificationError("WORK_ITEM_NOT_OBJECT")
        work_id = item.get("work_id")
        if not isinstance(work_id, str) or not work_id:
            raise ClassificationError("WORK_ID_INVALID")
        if work_id in ids:
            raise ClassificationError(f"WORK_ID_DUPLICATE:{work_id}")
        ids.add(work_id)
        head = item.get("current_head")
        if not isinstance(head, str) or not HEX40_64.fullmatch(head):
            raise ClassificationError(f"CURRENT_HEAD_INVALID:{work_id}")


def validate_evidence(doc: Mapping[str, Any], lineage: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != EVIDENCE_SCHEMA:
        raise ClassificationError("UNSUPPORTED_EVIDENCE_SCHEMA")
    if doc.get("authority") != "CLASSIFICATION_EVIDENCE_ONLY":
        raise ClassificationError("EVIDENCE_AUTHORITY_UNSUPPORTED")
    if not isinstance(doc.get("complete"), bool):
        raise ClassificationError("EVIDENCE_COMPLETENESS_INVALID")
    if doc.get("source_lineage_manifest_sha256") != lineage.get("manifest_sha256"):
        raise ClassificationError("EVIDENCE_LINEAGE_BINDING_MISMATCH")
    work = doc.get("work")
    if not isinstance(work, dict):
        raise ClassificationError("EVIDENCE_WORK_NOT_OBJECT")
    known_ids = {str(item["work_id"]) for item in lineage["work_items"]}
    unknown = sorted(set(work) - known_ids)
    if unknown:
        raise ClassificationError("EVIDENCE_UNKNOWN_WORK:" + ",".join(unknown))
    for work_id, record in work.items():
        if not isinstance(record, dict):
            raise ClassificationError(f"EVIDENCE_RECORD_NOT_OBJECT:{work_id}")
        head = record.get("observed_head")
        if not isinstance(head, str) or not HEX40_64.fullmatch(head):
            raise ClassificationError(f"EVIDENCE_HEAD_INVALID:{work_id}")
        if record.get("mergeable") not in {True, False, None}:
            raise ClassificationError(f"EVIDENCE_MERGEABLE_INVALID:{work_id}")
        if not isinstance(record.get("exact_head_verified"), bool):
            raise ClassificationError(f"EVIDENCE_VERIFIED_INVALID:{work_id}")
        for key in ("expected_parent_sha", "current_parent_sha"):
            value = record.get(key)
            if value is not None and (not isinstance(value, str) or not HEX40_64.fullmatch(value)):
                raise ClassificationError(f"EVIDENCE_PARENT_SHA_INVALID:{work_id}:{key}")
        string_list(record.get("blockers", []), f"{work_id}.blockers")
        roots = string_list(record.get("verification_roots", []), f"{work_id}.verification_roots")
        unique = string_list(record.get("unique_capability_evidence_roots", []), f"{work_id}.unique_capability_evidence_roots")
        if not all(HEX64.fullmatch(root) for root in roots + unique):
            raise ClassificationError(f"EVIDENCE_ROOT_INVALID:{work_id}")
        if not isinstance(record.get("recovery_required"), bool):
            raise ClassificationError(f"EVIDENCE_RECOVERY_INVALID:{work_id}")
        proof = record.get("containment_proof")
        if proof is not None and not isinstance(proof, dict):
            raise ClassificationError(f"CONTAINMENT_PROOF_NOT_OBJECT:{work_id}")


def valid_containment(proof: Mapping[str, Any] | None, current_head: str) -> bool:
    if proof is None:
        return False
    if proof.get("method") != "GIT_MERGE_BASE_IS_ANCESTOR":
        return False
    if proof.get("verified") is not True:
        return False
    if proof.get("candidate_head") != current_head:
        return False
    container_ref = proof.get("container_ref")
    container_head = proof.get("container_head")
    return (
        isinstance(container_ref, str)
        and bool(container_ref)
        and isinstance(container_head, str)
        and bool(HEX40_64.fullmatch(container_head))
    )


def classify_one(
    item: Mapping[str, Any],
    evidence_record: Mapping[str, Any] | None,
    *,
    lineage_complete: bool,
    evidence_complete: bool,
    active_spine: set[str],
) -> dict[str, Any]:
    work_id = str(item["work_id"])
    current_head = str(item["current_head"])
    reasons: list[str] = []
    evidence_roots: list[str] = []

    # Historical/supersession metadata is preserved independently of current PR
    # mergeability or verification status.
    if item.get("classification") == "HISTORICAL_EVIDENCE_ONLY":
        classification = "HISTORICAL_EVIDENCE_ONLY"
        reasons.append("DECLARED_HISTORICAL_RECONCILED_WORK")
    elif item.get("superseded_by") is not None:
        classification = "SUPERSEDED_BY"
        reasons.append(f"SUPERSEDED_BY:{item['superseded_by']}")
    elif evidence_record is None:
        if work_id in active_spine and lineage_complete:
            classification = "ACTIVE_SPINE"
            reasons.append("ACTIVE_SPINE_EVIDENCE_NOT_YET_REEVALUATED")
        else:
            classification = "UNKNOWN_FAIL_CLOSED"
            reasons.append("CLASSIFICATION_EVIDENCE_MISSING")
            if not evidence_complete:
                reasons.append("EVIDENCE_DISCOVERY_INCOMPLETE")
    else:
        observed_head = str(evidence_record["observed_head"])
        evidence_roots = sorted(
            set(string_list(evidence_record.get("verification_roots", []), f"{work_id}.verification_roots"))
            | set(string_list(evidence_record.get("unique_capability_evidence_roots", []), f"{work_id}.unique_capability_evidence_roots"))
        )
        proof = evidence_record.get("containment_proof")

        if evidence_record.get("recovery_required") is True:
            classification = "RECOVERY_REQUIRED"
            reasons.append("RECOVERY_EVIDENCE_REQUIRED_BEFORE_DISPOSITION")
        elif proof is not None and not valid_containment(proof, current_head):
            classification = "UNKNOWN_FAIL_CLOSED"
            reasons.append("INVALID_OR_STALE_CONTAINMENT_PROOF")
        elif valid_containment(proof, current_head):
            classification = "REDUNDANT_PROVEN"
            reasons.extend([
                "MECHANICAL_CONTAINMENT_VERIFIED",
                f"CONTAINER_REF:{proof['container_ref']}",
                f"CONTAINER_HEAD:{proof['container_head']}",
            ])
        elif string_list(evidence_record.get("blockers", []), f"{work_id}.blockers"):
            blockers = string_list(evidence_record.get("blockers", []), f"{work_id}.blockers")
            classification = "BLOCKED"
            reasons.extend([f"BLOCKER:{blocker}" for blocker in blockers])
        elif string_list(evidence_record.get("unique_capability_evidence_roots", []), f"{work_id}.unique_capability_evidence_roots"):
            classification = "UNIQUE_SIDE_CAPABILITY"
            reasons.append("UNIQUE_CAPABILITY_EVIDENCE_PRESENT")
        elif work_id in active_spine:
            expected_parent = evidence_record.get("expected_parent_sha")
            current_parent = evidence_record.get("current_parent_sha")
            if observed_head != current_head:
                classification = "NEEDS_REVERIFY"
                reasons.append("HEAD_SHA_CHANGED")
            elif expected_parent is not None and current_parent is not None and expected_parent != current_parent:
                classification = "NEEDS_REVERIFY"
                reasons.append("PARENT_SHA_CHANGED")
            elif (
                evidence_record.get("exact_head_verified") is True
                and evidence_record.get("mergeable") is True
                and item.get("draft") is False
                and lineage_complete
                and evidence_complete
            ):
                classification = "READY_TO_ADMIT"
                reasons.extend([
                    "EXACT_HEAD_VERIFIED",
                    "PARENT_BINDING_CURRENT",
                    "MERGEABLE_OBSERVED",
                    "NON_DRAFT",
                    "DISCOVERY_COMPLETE",
                ])
            else:
                classification = "ACTIVE_SPINE"
                if evidence_record.get("mergeable") is True:
                    reasons.append("MERGEABLE_IS_NOT_SUFFICIENT")
                if evidence_record.get("exact_head_verified") is not True:
                    reasons.append("EXACT_HEAD_VERIFICATION_NOT_ESTABLISHED")
                if item.get("draft") is True:
                    reasons.append("DRAFT_NOT_READY_TO_ADMIT")
                if not lineage_complete or not evidence_complete:
                    reasons.append("DISCOVERY_INCOMPLETE")
        else:
            classification = "UNKNOWN_FAIL_CLOSED"
            reasons.append("NO_DISPOSITION_EVIDENCE")

    if classification not in CLASSIFICATIONS:
        raise ClassificationError(f"INTERNAL_CLASSIFICATION_INVALID:{work_id}")

    return {
        "work_id": work_id,
        "subject_head": current_head,
        "classification": classification,
        "reasons": sorted(set(reasons)),
        "evidence_roots": evidence_roots,
        # Classification is evidence; it never directly grants destructive authority.
        "destructive_action_allowed": False,
        # Task 7 may consider this candidate, but must independently re-prove
        # containment against the exact current tip immediately before deletion.
        "cleanup_candidate_eligible": classification == "REDUNDANT_PROVEN",
        "canonical_merge_candidate_eligible": classification == "READY_TO_ADMIT",
    }


def build_classification(lineage: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    validate_lineage(lineage)
    validate_evidence(evidence, lineage)
    active = set(str(x) for x in lineage.get("active_spine", []))
    work_evidence = evidence["work"]
    classifications = [
        classify_one(
            item,
            work_evidence.get(str(item["work_id"])),
            lineage_complete=bool(lineage["discovery_complete"]),
            evidence_complete=bool(evidence["complete"]),
            active_spine=active,
        )
        for item in lineage["work_items"]
    ]
    classifications.sort(key=lambda x: x["work_id"])

    counts = {name: 0 for name in sorted(CLASSIFICATIONS)}
    for item in classifications:
        counts[item["classification"]] += 1

    evidence_digest = hash_doc(EVIDENCE_DOMAIN, evidence)
    body: dict[str, Any] = {
        "schema_version": OUTPUT_SCHEMA,
        "authority": "CLASSIFICATION_EVIDENCE_ONLY",
        "repository": lineage["repository"],
        "source_lineage_manifest_sha256": lineage["manifest_sha256"],
        "source_evidence_sha256": evidence_digest,
        "lineage_discovery_complete": lineage["discovery_complete"],
        "classification_evidence_complete": evidence["complete"],
        "classifications": classifications,
        "counts": counts,
        "rules": [
            "MERGEABLE_ALONE_NEVER_MEANS_READY_TO_ADMIT",
            "UNKNOWN_FAIL_CLOSED_NEVER_AUTHORIZES_MUTATION",
            "REDUNDANT_PROVEN_REQUIRES_EXACT_MECHANICAL_CONTAINMENT",
            "CLASSIFICATION_IS_EVIDENCE_NOT_EXECUTION_AUTHORITY",
        ],
    }
    return {**body, "manifest_sha256": hash_doc(OUTPUT_DOMAIN, body)}


def decision_record(body: Mapping[str, Any]) -> dict[str, Any]:
    return {**body, "record_digest": hash_doc(DECISION_DOMAIN, body)}


def build_decision_chain(classification: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    genesis_body: dict[str, Any] = {
        "schema_version": DECISION_SCHEMA,
        "record_kind": "GENESIS",
        "chain_index": 0,
        "previous_digest": None,
        "authority": "EVIDENCE_ONLY_NO_MUTATION_AUTHORITY",
        "action": "CLASSIFICATION_CENSUS_START",
        "source_lineage_manifest_sha256": classification["source_lineage_manifest_sha256"],
        "source_evidence_sha256": classification["source_evidence_sha256"],
        "classification_manifest_sha256": classification["manifest_sha256"],
    }
    genesis = decision_record(genesis_body)
    records.append(genesis)
    previous = genesis["record_digest"]

    for index, item in enumerate(classification["classifications"], start=1):
        body = {
            "schema_version": DECISION_SCHEMA,
            "record_kind": "CLASSIFICATION",
            "chain_index": index,
            "previous_digest": previous,
            "authority": "EVIDENCE_ONLY_NO_MUTATION_AUTHORITY",
            "action": "NO_MUTATION",
            "work_id": item["work_id"],
            "subject_head": item["subject_head"],
            "classification": item["classification"],
            "reasons": item["reasons"],
            "evidence_roots": item["evidence_roots"],
            "cleanup_candidate_eligible": item["cleanup_candidate_eligible"],
            "canonical_merge_candidate_eligible": item["canonical_merge_candidate_eligible"],
        }
        record = decision_record(body)
        records.append(record)
        previous = record["record_digest"]
    return records


def write_decisions(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for record in records)
    path.write_text(text, encoding="utf-8")


def verify_decisions(path: Path) -> None:
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ClassificationError(f"DECISION_LEDGER_READ_FAILED:{exc}") from exc
    if not raw_lines:
        raise ClassificationError("DECISION_LEDGER_EMPTY")
    previous: str | None = None
    for expected_index, line in enumerate(raw_lines):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ClassificationError(f"DECISION_JSON_INVALID:{expected_index}") from exc
        if not isinstance(record, dict):
            raise ClassificationError(f"DECISION_NOT_OBJECT:{expected_index}")
        if record.get("schema_version") != DECISION_SCHEMA:
            raise ClassificationError(f"DECISION_SCHEMA_INVALID:{expected_index}")
        if record.get("chain_index") != expected_index:
            raise ClassificationError(f"DECISION_INDEX_INVALID:{expected_index}")
        if record.get("previous_digest") != previous:
            raise ClassificationError(f"DECISION_PREVIOUS_DIGEST_INVALID:{expected_index}")
        actual = record.get("record_digest")
        if not isinstance(actual, str) or not HEX64.fullmatch(actual):
            raise ClassificationError(f"DECISION_DIGEST_INVALID:{expected_index}")
        body = dict(record)
        body.pop("record_digest", None)
        expected = hash_doc(DECISION_DOMAIN, body)
        if actual != expected:
            raise ClassificationError(f"DECISION_TAMPER_DETECTED:{expected_index}")
        previous = actual


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lineage", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--verify-decisions", type=Path)
    args = parser.parse_args(argv)
    if args.verify_decisions is not None:
        if any(x is not None for x in (args.lineage, args.evidence, args.out, args.decisions)):
            parser.error("--verify-decisions is exclusive")
    elif any(x is None for x in (args.lineage, args.evidence, args.out, args.decisions)):
        parser.error("--lineage --evidence --out --decisions are required together")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.verify_decisions is not None:
            verify_decisions(args.verify_decisions)
            print(json.dumps({"decision_chain": "VALID", "path": str(args.verify_decisions)}, sort_keys=True))
            return 0

        lineage = load_object(args.lineage)
        evidence = load_object(args.evidence)
        classification = build_classification(lineage, evidence)
        records = build_decision_chain(classification)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(classification, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_decisions(args.decisions, records)
        verify_decisions(args.decisions)
    except ClassificationError as exc:
        print(f"classify-reconciliation: FAIL_CLOSED {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "schema_version": classification["schema_version"],
        "work_item_count": len(classification["classifications"]),
        "counts": classification["counts"],
        "manifest_sha256": classification["manifest_sha256"],
        "decision_terminal_digest": records[-1]["record_digest"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
