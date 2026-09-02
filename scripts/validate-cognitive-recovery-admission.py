#!/usr/bin/env python3
"""Deterministic primitives for AEGIS cognitive recovery admission.

This module is intentionally non-mutating. It provides canonical serialization,
content-addressed request identity, and deterministic authority-none recovery
admission receipts. It grants no repository, cloud, deployment, billing, or
mathematical mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

REQUEST_DOMAIN = "AEGIS_COGNITIVE_RECOVERY_ADMISSION_REQUEST_V1"
RECEIPT_DOMAIN = "AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1"
RECEIPT_KIND = "AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1"
SCHEMA_VERSION = "1.0.0"
REPOSITORY_ID = "Aegis-Omega/AEGIS-OMEGA"
SCOPE = "ONE_EXACT_CANONICAL_RECOVERY_TRANSITION"
VERIFIER_IDENTITY = "offline:aegis-cognitive-recovery-admission-v1"
GRANTED = "RECOVERY_ADMISSION_GRANTED"
DENIED = "DENIED"


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes and reject non-finite numbers."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return lowercase hexadecimal SHA-256 for exact bytes."""
    return hashlib.sha256(data).hexdigest()


def request_digest(request: dict[str, Any]) -> str:
    """Hash a recovery request while excluding only its self-referential id."""
    body = {key: value for key, value in request.items() if key != "request_id"}
    envelope = {"domain": REQUEST_DOMAIN, "request": body}
    return sha256_hex(canonical_bytes(envelope))


def build_receipt(
    *,
    request: dict[str, Any],
    platform_governance_state: str,
    verified_gates: list[str],
    violations: list[str],
    outcome: str,
    verifier_code_digest: str,
) -> dict[str, Any]:
    """Build a deterministic non-mutating recovery admission decision receipt."""
    if outcome not in {GRANTED, DENIED}:
        raise ValueError(f"unsupported recovery admission outcome: {outcome}")

    authority = "RECOVERY_ADMISSION_ONLY" if outcome == GRANTED else "NONE"
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
        "verified_gates": sorted(verified_gates),
        "violations": sorted(set(violations)),
        "outcome": outcome,
        "scope": SCOPE,
        "authority": authority,
        "mutation_authority": "NONE",
        "verifier_identity": VERIFIER_IDENTITY,
        "verifier_code_digest": verifier_code_digest,
    }
    body["receipt_hash"] = sha256_hex(
        canonical_bytes({"domain": RECEIPT_DOMAIN, "receipt": body})
    )
    return body
