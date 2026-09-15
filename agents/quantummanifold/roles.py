"""Role-context isolation gates for QuantumManifold Scheduler v0.1."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_ROLE_POLICY = {
    "BUILDER": "PRESERVE",
    "FALSIFIER": "RAW_EVIDENCE_ONLY",
    "REVIEWER": "CLEAN_ROOM",
}
_BASE_FIELDS = {
    "receipt_kind",
    "role",
    "inheritance_policy",
    "baseline_digest",
    "source_head_sha",
    "reality_snapshot_digest",
    "selected_action_digest",
    "obligation_digest",
    "scheduler_receipt_digest",
    "role_policy_digest",
    "input_evidence_roots",
    "continuation_state_digest",
    "authority_effect",
}
_DIGEST_FIELDS = (
    "baseline_digest",
    "reality_snapshot_digest",
    "selected_action_digest",
    "obligation_digest",
    "scheduler_receipt_digest",
    "role_policy_digest",
)


def _require_digest(value: object) -> None:
    if not isinstance(value, str) or _HEX64_RE.fullmatch(value) is None:
        raise ValueError("INVALID_ROLE_CONTEXT")


def validate_role_context(context: object) -> None:
    """Validate role inheritance and reject prose/continuation authority leakage."""
    if not isinstance(context, Mapping):
        raise ValueError("INVALID_ROLE_CONTEXT")

    role = context.get("role")
    inheritance = context.get("inheritance_policy")
    if role not in _ROLE_POLICY or inheritance != _ROLE_POLICY[role]:
        raise ValueError("ROLE_ISOLATION_VIOLATION")

    if context.get("authority_effect") != "NONE":
        raise ValueError("AUTHORITY_TUNNELING_ATTEMPT")

    if role == "FALSIFIER" and context.get("continuation_state_digest") is not None:
        raise ValueError("ROLE_ISOLATION_VIOLATION")

    reviewer_forbidden = {
        "prose_continuation",
        "builder_prose",
        "falsifier_prose",
        "prior_reviewer_opinion",
        "hidden_model_continuation_state",
    }
    if role == "REVIEWER" and any(key in context for key in reviewer_forbidden):
        raise ValueError("CLEAN_ROOM_VIOLATION")
    if role == "REVIEWER" and context.get("continuation_state_digest") is not None:
        raise ValueError("CLEAN_ROOM_VIOLATION")

    if set(context.keys()) != _BASE_FIELDS:
        raise ValueError("INVALID_ROLE_CONTEXT")
    if context.get("receipt_kind") != "AEGIS_ROLE_CONTEXT_ENVELOPE_V1":
        raise ValueError("INVALID_ROLE_CONTEXT")

    for field in _DIGEST_FIELDS:
        _require_digest(context.get(field))

    source_head = context.get("source_head_sha")
    if not isinstance(source_head, str) or _SHA1_RE.fullmatch(source_head) is None:
        raise ValueError("SOURCE_HEAD_INVALID")

    continuation = context.get("continuation_state_digest")
    if continuation is not None:
        _require_digest(continuation)

    roots = context.get("input_evidence_roots")
    if isinstance(roots, (str, bytes, bytearray)) or not isinstance(roots, Sequence):
        raise ValueError("INVALID_ROLE_CONTEXT")
    for root in roots:
        _require_digest(root)
