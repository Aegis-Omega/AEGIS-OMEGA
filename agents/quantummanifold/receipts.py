"""Deterministic scheduling receipts for QuantumManifold Scheduler v0.1.

Scheduling receipts are recommendation evidence only. They always carry
``authority_effect = NONE`` and cannot transport admission or execution authority.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from .bindings import validate_baseline_digest
from .fixed_point import require_canonical_metric

RECEIPT_KIND = "AEGIS_QUANTUMMANIFOLD_SCHEDULING_RECEIPT_V1"
_ALLOWED_ROLES = {"BUILDER", "FALSIFIER", "REVIEWER"}
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_FIELDS = (
    "baseline_digest",
    "reality_snapshot_digest",
    "obligation_set_digest",
    "candidate_set_digest",
    "scheduler_policy_digest",
    "selected_action_digest",
)
_SCORE_FIELDS = (
    "information_gain_ppm",
    "closure_leverage_ppm",
    "falsification_value_ppm",
    "cost_ppm",
    "ranking_score_ppm",
)
_REQUIRED_FIELDS = {
    "receipt_kind",
    "baseline_digest",
    "source_head_sha",
    "reality_snapshot_digest",
    "obligation_set_digest",
    "candidate_set_digest",
    "scheduler_policy_digest",
    "selected_action_digest",
    "score_components_fixed_point",
    "recommended_role",
    "authority_effect",
}


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Canonical bytes for this fixed ASCII-key, integer/string receipt domain."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def validate_scheduling_receipt(receipt: object) -> None:
    """Validate the normative receipt shape and fail closed on authority tunneling."""
    if not isinstance(receipt, Mapping):
        raise ValueError("INVALID_SCHEDULING_RECEIPT")

    if receipt.get("authority_effect") != "NONE":
        raise ValueError("AUTHORITY_TUNNELING_ATTEMPT")

    if set(receipt.keys()) != _REQUIRED_FIELDS:
        raise ValueError("INVALID_SCHEDULING_RECEIPT")
    if receipt.get("receipt_kind") != RECEIPT_KIND:
        raise ValueError("INVALID_SCHEDULING_RECEIPT")
    if receipt.get("recommended_role") not in _ALLOWED_ROLES:
        raise ValueError("INVALID_RECOMMENDED_ROLE")

    baseline = receipt.get("baseline_digest")
    if not isinstance(baseline, str):
        raise ValueError("BASELINE_BINDING_MISMATCH")
    validate_baseline_digest(baseline)

    for field in _DIGEST_FIELDS:
        value = receipt.get(field)
        if not isinstance(value, str) or _HEX64_RE.fullmatch(value) is None:
            raise ValueError("INVALID_SCHEDULING_RECEIPT")

    source_head = receipt.get("source_head_sha")
    if not isinstance(source_head, str) or _SHA1_RE.fullmatch(source_head) is None:
        raise ValueError("SOURCE_HEAD_INVALID")

    scores = receipt.get("score_components_fixed_point")
    if not isinstance(scores, Mapping) or set(scores.keys()) != set(_SCORE_FIELDS):
        raise ValueError("INVALID_SCHEDULING_RECEIPT")
    for field in _SCORE_FIELDS:
        require_canonical_metric(scores[field])


def build_scheduling_receipt(
    *,
    baseline_digest: str,
    source_head_sha: str,
    reality_snapshot_digest: str,
    obligation_set_digest: str,
    candidate_set_digest: str,
    scheduler_policy_digest: str,
    selected_action_digest: str,
    score_components_fixed_point: Mapping[str, object],
    recommended_role: str,
) -> bytes:
    """Build byte-stable recommendation evidence with no authority effect."""
    receipt: dict[str, Any] = {
        "receipt_kind": RECEIPT_KIND,
        "baseline_digest": baseline_digest,
        "source_head_sha": source_head_sha,
        "reality_snapshot_digest": reality_snapshot_digest,
        "obligation_set_digest": obligation_set_digest,
        "candidate_set_digest": candidate_set_digest,
        "scheduler_policy_digest": scheduler_policy_digest,
        "selected_action_digest": selected_action_digest,
        "score_components_fixed_point": dict(score_components_fixed_point),
        "recommended_role": recommended_role,
        "authority_effect": "NONE",
    }
    validate_scheduling_receipt(receipt)
    return _canonical_json_bytes(receipt)
