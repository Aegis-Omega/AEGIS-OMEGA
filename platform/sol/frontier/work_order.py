from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Iterable

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_SECRET_REF_PREFIXES = ("secret://", "env://", "vault://", "keyref://", "oidc://", "identity://")
_ALLOWED_CONSEQUENCE_CLASSES = {"D0", "D1", "D2", "D3", "D4"}


class WorkOrderError(ValueError):
    pass


def _require_text(value: str, name: str, minimum: int = 1) -> None:
    if not isinstance(value, str) or len(value) < minimum:
        raise WorkOrderError(f"{name} is required")


def _require_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise WorkOrderError(f"{name} must be a lowercase SHA-256 hex digest")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class ProofCarryingWorkOrder:
    work_order_id: str
    request_id: str
    provider: str
    capability: str
    target: str
    consequence_class: str
    arguments_digest: str
    expected_parent_state_root: str
    idempotency_key: str
    max_cost_microusd: int
    max_input_tokens: int
    max_output_tokens: int
    evidence_references: tuple[str, ...]
    operator_approval_reference: str | None
    secret_references: tuple[str, ...]
    issued_sequence: int
    schema_version: str = "1.0.0"


@dataclass(frozen=True)
class VerifiedWorkOrder:
    order: ProofCarryingWorkOrder
    digest: str

    def assert_matches(
        self,
        *,
        provider: str,
        capability: str,
        target: str,
        request_id: str,
        arguments_digest: str | None = None,
        expected_parent_state_root: str | None = None,
        idempotency_key: str | None = None,
        max_cost_microusd: int | None = None,
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        if self.order.provider != provider:
            raise WorkOrderError("work order provider does not match invocation")
        if self.order.capability != capability:
            raise WorkOrderError("work order capability does not match invocation")
        if self.order.target != target:
            raise WorkOrderError("work order target does not match invocation")
        if self.order.request_id != request_id:
            raise WorkOrderError("work order request_id does not match invocation")
        if arguments_digest is not None and self.order.arguments_digest != arguments_digest:
            raise WorkOrderError("work order arguments_digest does not match invocation")
        if expected_parent_state_root is not None and self.order.expected_parent_state_root != expected_parent_state_root:
            raise WorkOrderError("work order expected parent does not match invocation")
        if idempotency_key is not None and self.order.idempotency_key != idempotency_key:
            raise WorkOrderError("work order idempotency_key does not match invocation")
        if max_cost_microusd is not None and self.order.max_cost_microusd < max_cost_microusd:
            raise WorkOrderError("invocation cost ceiling exceeds work order")
        if max_input_tokens is not None and self.order.max_input_tokens < max_input_tokens:
            raise WorkOrderError("invocation input token ceiling exceeds work order")
        if max_output_tokens is not None and self.order.max_output_tokens < max_output_tokens:
            raise WorkOrderError("invocation output token ceiling exceeds work order")


def _validate_references(values: Iterable[str], name: str) -> tuple[str, ...]:
    normalized = tuple(values)
    for value in normalized:
        _require_text(value, name)
        if any(token in value.lower() for token in ("bearer ", "api_key=", "apikey=", "authorization:")):
            raise WorkOrderError(f"{name} contains inline credential material")
    return normalized


def verify_work_order(order: ProofCarryingWorkOrder) -> VerifiedWorkOrder:
    if order.schema_version != "1.0.0":
        raise WorkOrderError("unsupported work order schema_version")
    for name in ("work_order_id", "request_id", "provider", "capability", "target"):
        _require_text(getattr(order, name), name)
    _require_text(order.idempotency_key, "idempotency_key", minimum=8)
    _require_sha256(order.arguments_digest, "arguments_digest")
    _require_sha256(order.expected_parent_state_root, "expected_parent_state_root")

    if order.consequence_class not in _ALLOWED_CONSEQUENCE_CLASSES:
        raise WorkOrderError("unknown consequence_class")
    if order.consequence_class == "D4":
        raise WorkOrderError("D4 work is denied until a dedicated admitted policy exists")
    if order.issued_sequence < 0:
        raise WorkOrderError("issued_sequence must be non-negative")
    if order.max_cost_microusd < 0:
        raise WorkOrderError("max_cost_microusd must be non-negative")
    if order.max_input_tokens < 0 or order.max_output_tokens < 0:
        raise WorkOrderError("token limits must be non-negative")

    evidence_references = _validate_references(order.evidence_references, "evidence_reference")
    if order.consequence_class in {"D2", "D3"} and not evidence_references:
        raise WorkOrderError("D2/D3 work requires evidence references")

    if order.consequence_class == "D3":
        if order.operator_approval_reference is None:
            raise WorkOrderError("D3 work requires explicit operator approval")
        _require_text(order.operator_approval_reference, "operator_approval_reference")
        _validate_references((order.operator_approval_reference,), "operator_approval_reference")

    for reference in order.secret_references:
        _require_text(reference, "secret_reference")
        if not reference.startswith(_SECRET_REF_PREFIXES):
            raise WorkOrderError("secret references must be opaque references, never secret material")

    payload = {
        "schema_version": order.schema_version,
        "work_order_id": order.work_order_id,
        "request_id": order.request_id,
        "provider": order.provider,
        "capability": order.capability,
        "target": order.target,
        "consequence_class": order.consequence_class,
        "arguments_digest": order.arguments_digest,
        "expected_parent_state_root": order.expected_parent_state_root,
        "idempotency_key": order.idempotency_key,
        "max_cost_microusd": order.max_cost_microusd,
        "max_input_tokens": order.max_input_tokens,
        "max_output_tokens": order.max_output_tokens,
        "evidence_references": list(order.evidence_references),
        "operator_approval_reference": order.operator_approval_reference,
        "secret_references": list(order.secret_references),
        "issued_sequence": order.issued_sequence,
    }
    return VerifiedWorkOrder(order=order, digest=sha256(_canonical_json(payload)).hexdigest())
