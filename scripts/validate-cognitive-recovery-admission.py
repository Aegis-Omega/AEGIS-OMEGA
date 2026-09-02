#!/usr/bin/env python3
"""Deterministic, offline primitives for Cognitive Recovery Admission V1.

This milestone is authority-neutral. It does not sign, mutate refs, update main,
modify repository governance, deploy, or grant production recovery authority.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

RECEIPT_KIND = "AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1"
REQUEST_DOMAIN = "AEGIS_COGNITIVE_RECOVERY_ADMISSION_REQUEST_V1"
SCHEMA_VERSION = "1.0.0"
VERIFIER_IDENTITY = "offline:aegis-cognitive-recovery-admission-v1"


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic compact UTF-8 JSON; reject NaN/Infinity."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request_digest(request: dict[str, Any]) -> str:
    """Bind every request field except the self-identifying request_id."""
    body = {key: value for key, value in request.items() if key != "request_id"}
    return sha256_hex(
        canonical_bytes({"domain": REQUEST_DOMAIN, "request": body})
    )


def build_receipt(
    *,
    request: dict[str, Any],
    verified_gates: Iterable[str],
    violations: Iterable[str],
    platform_governance_state: str,
    verifier_code_digest: str,
) -> dict[str, Any]:
    """Build a deterministic authority-bounded admission decision receipt."""
    gates = list(verified_gates)
    violation_list = list(violations)
    granted = len(violation_list) == 0

    body: dict[str, Any] = {
        "receipt_kind": RECEIPT_KIND,
        "schema_version": SCHEMA_VERSION,
        "request_digest": request_digest(request),
        "repository_id": request["repository_id"],
        "candidate_sha": request["candidate_sha"],
        "denied_base_sha": request["denied_base_sha"],
        "trusted_control_plane_sha": request["trusted_control_plane_sha"],
        "recovery_parent_sha": request["recovery_parent_sha"],
        "recovery_receipt_hash": request["recovery_receipt_hash"],
        "writer_workflow_blob": request["writer_workflow_blob"],
        "platform_governance_observation_digest": request[
            "platform_governance_observation_digest"
        ],
        "platform_governance_state": platform_governance_state,
        "operator_approval_digest": request["operator_approval_digest"],
        "verified_gates": gates,
        "violations": violation_list,
        "outcome": "RECOVERY_ADMISSION_GRANTED" if granted else "DENIED",
        "scope": "ONE_EXACT_CANONICAL_RECOVERY_TRANSITION",
        "authority": "RECOVERY_ADMISSION_ONLY" if granted else "NONE",
        "mutation_authority": "NONE",
        "verifier_identity": VERIFIER_IDENTITY,
        "verifier_code_digest": verifier_code_digest,
    }
    receipt_hash = sha256_hex(
        canonical_bytes({"domain": RECEIPT_KIND, "receipt": body})
    )
    return {**body, "receipt_hash": receipt_hash}
