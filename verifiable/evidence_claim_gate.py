#!/usr/bin/env python3
"""Domain-independent contract validation for evidence-based claims.

The gate checks logical/provenance integrity, not truth of remote evidence.
Never convert a missing/failing probe into mathematical/operational refutation.
Stdlib-only, no network or side effects.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "aegis.evidence-claim.v1"
STATUSES = {"VERIFIED", "REFUTED", "OPEN", "UNKNOWN", "BLOCKED"}
OBSERVATIONS = {"PASS", "FAIL", "COUNTEREXAMPLE", "UNOBSERVED"}
PRIMARY_KINDS = {"kernel", "compiler", "test", "runtime", "provider_record", "measurement", "signed_receipt", "counterexample"}
NONPRIMARY_KINDS = {"comment", "docstring", "metadata", "pr_description", "assistant_summary", "issue", "readme"}
SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
GIT_RE = re.compile(r"^[a-fA-F0-9]{40}$")


def validate(claim: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if claim.get("schema") != SCHEMA:
        errors.append("schema: expected aegis.evidence-claim.v1")
    if not isinstance(claim.get("claim_id"), str) or not claim["claim_id"].strip():
        errors.append("claim_id: required")
    if not isinstance(claim.get("target"), str) or not claim["target"].strip():
        errors.append("target: exact subject/claim required")
    status = claim.get("status")
    if status not in STATUSES:
        errors.append("status: must be one of VERIFIED, REFUTED, OPEN, UNKNOWN, BLOCKED")
    scope = claim.get("scope")
    if not isinstance(scope, dict) or not scope.get("description"):
        errors.append("scope: nonempty description required")
        scope = {}
    rev = scope.get("revision")
    if rev is not None and not (isinstance(rev, str) and (GIT_RE.fullmatch(rev) or rev.startswith("record:"))):
        errors.append("scope.revision: full 40-character Git SHA or stable record:identifier required")
    if scope.get("universal") is True and scope.get("coverage_complete") is not True:
        errors.append("scope: universal claim requires independently attested coverage_complete=true")
    inventory = claim.get("inventory")
    if inventory is not None:
        if not isinstance(inventory, dict):
            errors.append("inventory: object required")
        elif inventory.get("complete") is True:
            items = inventory.get("items")
            total = inventory.get("reported_total")
            if not isinstance(items, list) or type(total) is not int or len(items) != total:
                errors.append("inventory: complete listing must match reported_total exactly")
    evidence = claim.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence: array required (can be empty for UNKNOWN/OPEN)")
        evidence = []
    observed_primary_pass = False
    observed_counterexample = False
    for n, item in enumerate(evidence):
        if not isinstance(item, dict):
            errors.append(f"evidence[{n}]: object required")
            continue
        kind = item.get("kind")
        observation = item.get("observation")
        if kind not in PRIMARY_KINDS | NONPRIMARY_KINDS:
            errors.append(f"evidence[{n}].kind: unsupported")
        if observation not in OBSERVATIONS:
            errors.append(f"evidence[{n}].observation: unsupported")
        if not item.get("uri") or not item.get("observed_at"):
            errors.append(f"evidence[{n}]: uri and observed_at required")
        digest = item.get("sha256")
        if digest is not None and (not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)):
            errors.append(f"evidence[{n}].sha256: 64 hex digits required")
        # A 'target_match' field is an assertion only. It must be accompanied
        # by a machine-observed primary check and an immutable witness identity.
        witness = bool(item.get("sha256") or item.get("revision") or item.get("record_id"))
        bound = item.get("target_match") is True and witness and item.get("observed_at") and item.get("uri")
        if kind in PRIMARY_KINDS and observation == "PASS" and bound:
            observed_primary_pass = True
        if kind == "counterexample" and observation == "COUNTEREXAMPLE" and bound:
            observed_counterexample = True
        if kind in NONPRIMARY_KINDS and observation in ("PASS", "COUNTEREXAMPLE"):
            # Such a note may be shown, but never upgrades the judgment.
            continue
    if status == "VERIFIED" and not observed_primary_pass:
        errors.append("VERIFIED: requires target-bound primary PASS evidence; metadata/green unrelated CI insufficient")
    if status == "REFUTED" and not observed_counterexample:
        errors.append("REFUTED: requires target-bound primary counterexample; failure/absence is not falsity")
    if status in {"UNKNOWN", "BLOCKED", "OPEN"} and claim.get("claim_is_false") is True:
        errors.append("uncertainty: claim_is_false cannot be inferred from missing/failed check")
    if "claim_is_false" in claim and type(claim["claim_is_false"]) is not bool:
        errors.append("claim_is_false: when present must be boolean")
    if status == "VERIFIED" and claim.get("claim_is_false") is True:
        errors.append("VERIFIED: contradictory claim_is_false=true")
    if status == "REFUTED" and claim.get("claim_is_false") is False:
        errors.append("REFUTED: contradictory claim_is_false=false")
    if claim.get("side_effects") is not None:
        effects = claim["side_effects"]
        if not isinstance(effects, dict) or type(effects.get("performed")) is not bool:
            errors.append("side_effects: object with performed boolean required")
        elif effects["performed"] is True and not (effects.get("operator_authorization_ref") and effects.get("exact_operations")):
            errors.append("side_effects: performed actions require actual operator authorization reference and exact operations")
    else:
        errors.append("side_effects: explicit performed=false or authorized effect record required")
    return errors


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: evidence_claim_gate.py RECEIPT.json", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"INVALID_RECEIPT: {exc}", file=sys.stderr)
        return 2
    failures = validate(data)
    if failures:
        for failure in failures:
            print(f"REJECT: {failure}", file=sys.stderr)
        return 1
    print(f"RECEIPT_STRUCTURE_VALID: {data['claim_id']} ({data['status']})")
    print("NOTE: This verifies consistency, NOT the external evidence itself.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())