"""Deterministic candidate/receipt schema for AEGIS Navier workflow V1."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

ALLOWED_TRANSITIONS = {
    "PROPOSED": {"TRIAGED", "FALSIFIED"},
    "TRIAGED": {"ACTIVE_RESEARCH", "FALSIFIED", "STALE"},
    "ACTIVE_RESEARCH": {"CANDIDATE_RESULT", "FALSIFIED", "DEPENDENCY_OPEN"},
    "CANDIDATE_RESULT": {"ADVERSARIAL_REVIEW", "FALSIFIED", "DEPENDENCY_OPEN"},
    "ADVERSARIAL_REVIEW": {"FORMALIZATION", "FALSIFIED", "DEPENDENCY_OPEN"},
    "FORMALIZATION": {"INDEPENDENT_REPLAY", "FORMALIZATION_FAILED", "DEPENDENCY_OPEN"},
    "INDEPENDENT_REPLAY": {"ADMISSION_REVIEW", "REPLAY_FAILED", "DEPENDENCY_OPEN"},
    "ADMISSION_REVIEW": {"TARGET_THEOREM_CLOSED", "DEPENDENCY_OPEN", "FALSIFIED"},
}

TARGET_CLOSURE_CHECKS = {
    "formal_kernel_pass",
    "independent_replay_pass",
    "exact_head_fresh",
}


def _reject_floats(value: Any) -> None:
    if isinstance(value, float):
        raise ValueError("floats are forbidden in canonical authority-bearing structures")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_floats(key)
            _reject_floats(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_floats(item)


def canonical_json(value: object) -> bytes:
    """Return NFC-normalized, key-sorted compact JSON bytes; floats fail closed."""
    _reject_floats(value)
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return unicodedata.normalize("NFC", text).encode("utf-8")


def sha256_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def transition_allowed(from_state: str, to_state: str) -> bool:
    return to_state in ALLOWED_TRANSITIONS.get(from_state, set())


def _require_fields(value: dict, required: set[str], kind: str) -> None:
    missing = sorted(required - value.keys())
    if missing:
        raise ValueError(f"missing {kind} fields: {missing}")


def validate_candidate(candidate: dict) -> dict:
    required = {
        "candidate_id",
        "lane_id",
        "claim",
        "claim_scope",
        "assumptions",
        "source_coordinates",
        "dependencies",
        "open_obligations",
        "known_failure_modes",
        "falsification_attempts",
        "artifact_digest",
    }
    _require_fields(candidate, required, "candidate")
    if candidate["claim_scope"] not in {
        "TARGET",
        "SURROGATE_ONLY",
        "ATTACK",
        "COUNTEREXAMPLE",
    }:
        raise ValueError("invalid claim scope")
    canonical_json(candidate)
    return dict(candidate)


def validate_receipt(receipt: dict) -> dict:
    required = {
        "schema",
        "transition_id",
        "candidate_id",
        "from_state",
        "to_state",
        "exact_head_sha",
        "input_artifact_digests",
        "output_artifact_digest",
        "assumptions",
        "open_obligations",
        "checks",
        "verifier_identity",
        "producer_identity",
        "verifier_independence_class",
        "decision",
        "claim_promotion",
        "authority_effect",
        "previous_receipt_digest",
    }
    _require_fields(receipt, required, "receipt")

    if receipt["schema"] != "AEGIS_NAVIER_RECEIPT_V1":
        raise ValueError("unsupported receipt schema")
    if not transition_allowed(receipt["from_state"], receipt["to_state"]):
        raise ValueError("invalid state transition")
    if (
        receipt["verifier_identity"] == receipt["producer_identity"]
        and receipt["verifier_independence_class"] == "INDEPENDENT"
    ):
        raise ValueError("a verifier cannot independently verify its own artifact")

    if receipt["to_state"] == "TARGET_THEOREM_CLOSED":
        if receipt["open_obligations"]:
            raise ValueError("open obligations block target closure")

        checks = set(receipt["checks"])
        missing = TARGET_CLOSURE_CHECKS - checks
        if missing == TARGET_CLOSURE_CHECKS:
            raise ValueError(
                f"required target-closure checks missing: {sorted(missing)}"
            )
        if "formal_kernel_pass" in missing:
            raise ValueError("formal kernel evidence is required for target closure")
        if "exact_head_fresh" in missing:
            raise ValueError("exact-head freshness is required for target closure")
        if missing:
            raise ValueError(
                f"required target-closure checks missing: {sorted(missing)}"
            )

        if receipt["authority_effect"] != "ELIGIBLE_FOR_ADMISSION_REVIEW_ONLY":
            raise ValueError("workflow cannot directly grant target authority")

    canonical_json(receipt)
    return dict(receipt)
