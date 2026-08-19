"""PR-5A serialized provider-execution evidence binding validator.

This module validates a cross-runtime evidence artifact. It never grants authority,
issues receipts, verifies world effects, or promotes provider output into effect truth.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from harness.sdk.sovereign_execution import canonical_hash

PROVIDER_EXECUTION_EVIDENCE_BINDING_KIND = "PROVIDER_EXECUTION_EVIDENCE_BINDING_V1"
PROVIDER_EXECUTION_EVIDENCE_BINDING_DOMAIN = "AEGIS_PROVIDER_EXECUTION_EVIDENCE_BINDING_V1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")
FIELD_ORDER = (
    "binding_kind",
    "provider",
    "request_id",
    "provider_operation_id",
    "response_digest",
    "work_order_digest",
    "authority_receipt_root",
    "transition_id",
    "execution_instance_id",
    "expected_parent_state_root",
    "grants_authority",
)


class ProviderExecutionBindingError(ValueError):
    pass


def _require_hash(name: str, value: Any) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ProviderExecutionBindingError(f"{name}:INVALID_SHA256")
    return value


def _require_id(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or SAFE_ID_RE.fullmatch(value) is None:
        raise ProviderExecutionBindingError(f"{name}:INVALID_ID")
    return value


@dataclass(frozen=True)
class ProviderExecutionEvidenceBinding:
    binding_kind: str
    provider: str
    request_id: str
    provider_operation_id: str
    response_digest: str
    work_order_digest: str
    authority_receipt_root: str
    transition_id: str
    execution_instance_id: str
    expected_parent_state_root: str
    grants_authority: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProviderExecutionEvidenceBinding":
        if not isinstance(value, Mapping) or set(value) != set(FIELD_ORDER):
            raise ProviderExecutionBindingError("PROVIDER_EXECUTION_BINDING_SCHEMA_DRIFT")
        binding = cls(**{name: value[name] for name in FIELD_ORDER})
        binding.validate()
        return binding

    def validate(self) -> None:
        if self.binding_kind != PROVIDER_EXECUTION_EVIDENCE_BINDING_KIND:
            raise ProviderExecutionBindingError("PROVIDER_EXECUTION_BINDING_KIND_MISMATCH")
        _require_id("provider", self.provider)
        _require_id("request_id", self.request_id)
        _require_id("provider_operation_id", self.provider_operation_id)
        _require_id("execution_instance_id", self.execution_instance_id)
        for name in (
            "response_digest",
            "work_order_digest",
            "authority_receipt_root",
            "transition_id",
            "expected_parent_state_root",
        ):
            _require_hash(name, getattr(self, name))
        if self.grants_authority is not False:
            raise ProviderExecutionBindingError("PROVIDER_EXECUTION_BINDING_AUTHORITY_ESCALATION")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash(PROVIDER_EXECUTION_EVIDENCE_BINDING_DOMAIN, asdict(self))


def verify_provider_execution_binding(
    binding: ProviderExecutionEvidenceBinding,
    *,
    binding_kind: str,
    provider: str,
    request_id: str,
    provider_operation_id: str,
    response_digest: str,
    work_order_digest: str,
    authority_receipt_root: str,
    transition_id: str,
    execution_instance_id: str,
    expected_parent_state_root: str,
    grants_authority: bool,
) -> bool:
    if type(binding) is not ProviderExecutionEvidenceBinding:
        return False
    try:
        binding.validate()
        expected = ProviderExecutionEvidenceBinding.from_mapping({
            "binding_kind": binding_kind,
            "provider": provider,
            "request_id": request_id,
            "provider_operation_id": provider_operation_id,
            "response_digest": response_digest,
            "work_order_digest": work_order_digest,
            "authority_receipt_root": authority_receipt_root,
            "transition_id": transition_id,
            "execution_instance_id": execution_instance_id,
            "expected_parent_state_root": expected_parent_state_root,
            "grants_authority": grants_authority,
        })
    except ProviderExecutionBindingError:
        return False
    return binding == expected
