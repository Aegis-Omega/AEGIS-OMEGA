from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .tools import EvidenceValidationError, validate_tool_output
from .types import OmegaRunContext, OmegaRunRequest, RuntimeErrorCode, ToolEvidence

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_AUTHORITY_SCORE_RE = re.compile(r"^(0|1)\.[0-9]{6}$")


class ReceiptConstructionError(ValueError):
    def __init__(self, code: RuntimeErrorCode, message: str):
        super().__init__(message)
        self.code = code


def _require_hash(name: str, value: str | None) -> str:
    if value is None or _HASH_RE.fullmatch(value) is None:
        raise ReceiptConstructionError(
            RuntimeErrorCode.RECEIPT_INCOMPLETE,
            f"{name} must be a lowercase SHA-256 hex digest",
        )
    return value


def _execution_identity_root(context: OmegaRunContext) -> str:
    payload = f"aegis-execution-v1|{context.execution_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_mutation_receipt(
    *,
    context: OmegaRunContext,
    request: OmegaRunRequest,
    evidence: ToolEvidence,
    workspace_binding: str,
    policy_decision_root: str,
    authority_score: str,
    authority_domain: str,
    requested_action_digest: str,
    parent_receipt: str,
    sequence: int,
) -> dict[str, Any]:
    """Construct the existing mutation-receipt.v1 shape from complete evidence only."""
    if not evidence.mutates:
        raise ReceiptConstructionError(
            RuntimeErrorCode.RECEIPT_INCOMPLETE,
            "read-only evidence must not be represented as a mutation receipt",
        )
    if not evidence.success:
        raise ReceiptConstructionError(
            RuntimeErrorCode.RECEIPT_INCOMPLETE,
            "v1 helper currently emits only successful mutation receipts",
        )

    try:
        validate_tool_output(evidence)
    except EvidenceValidationError as exc:
        raise ReceiptConstructionError(RuntimeErrorCode.RECEIPT_INCOMPLETE, str(exc)) from exc

    if _AUTHORITY_SCORE_RE.fullmatch(authority_score) is None:
        raise ReceiptConstructionError(
            RuntimeErrorCode.RECEIPT_INCOMPLETE,
            "authority_score must match mutation-receipt.v1 format",
        )
    if not authority_domain.strip():
        raise ReceiptConstructionError(
            RuntimeErrorCode.RECEIPT_INCOMPLETE,
            "authority_domain must not be blank",
        )
    if sequence < 0:
        raise ReceiptConstructionError(
            RuntimeErrorCode.RECEIPT_INCOMPLETE,
            "sequence must be non-negative",
        )

    receipt = {
        "receipt_version": "1.0.0",
        "execution_identity_root": _execution_identity_root(context),
        "workspace_binding": _require_hash("workspace_binding", workspace_binding),
        "policy_decision_root": _require_hash("policy_decision_root", policy_decision_root),
        "authority_score": authority_score,
        "authority_domain": authority_domain.strip(),
        "action_class": request.action_class.value,
        "tool": evidence.tool,
        "target": _require_hash("target_digest", evidence.target_digest),
        "pre_state_digest": _require_hash("pre_state_digest", evidence.pre_state_digest),
        "requested_action_digest": _require_hash("requested_action_digest", requested_action_digest),
        "result_digest": _require_hash("result_digest", evidence.result_digest),
        "post_state_digest": _require_hash("post_state_digest", evidence.post_state_digest),
        "parent_receipt": _require_hash("parent_receipt", parent_receipt),
        "sequence": sequence,
        "outcome": "SUCCEEDED",
        "denial_code": "NONE",
    }
    return receipt


def digest_receipt(receipt: dict[str, Any]) -> str:
    payload = json.dumps(
        receipt,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
