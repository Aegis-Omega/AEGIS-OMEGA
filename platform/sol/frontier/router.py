from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Protocol

from providers import ProviderRegistryError, get_provider
from work_order import ProofCarryingWorkOrder, WorkOrderError, verify_work_order


class RouterError(ValueError):
    pass


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def canonical_payload_digest(payload: object) -> str:
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RouterError("provider payload is not canonical-JSON serializable") from exc
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ProviderInvocation:
    request_id: str
    provider: str
    capability: str
    consequence_class: str
    arguments_digest: str
    expected_parent_state_root: str
    idempotency_key: str
    max_cost_microusd: int
    max_input_tokens: int
    max_output_tokens: int
    work_order: ProofCarryingWorkOrder | None = None
    payload: object | None = None


@dataclass(frozen=True)
class ProviderEvidence:
    provider: str
    capability: str
    request_id: str
    provider_operation_id: str
    response_digest: str
    status: str
    input_tokens: int
    output_tokens: int
    external_reference: str | None
    grants_authority: bool = False


class ProviderTransport(Protocol):
    provider: str

    def invoke(self, invocation: ProviderInvocation) -> ProviderEvidence:
        ...


class GovernedProviderRouter:
    def __init__(self, transports: list[ProviderTransport] | tuple[ProviderTransport, ...]):
        by_provider: dict[str, ProviderTransport] = {}
        for transport in transports:
            if transport.provider in by_provider:
                raise RouterError(f"duplicate transport for provider {transport.provider}")
            by_provider[transport.provider] = transport
        self._transports = by_provider
        self._idempotent: dict[tuple[str, str], ProviderEvidence] = {}

    def invoke(self, invocation: ProviderInvocation) -> ProviderEvidence:
        self._validate(invocation)
        key = (invocation.provider, invocation.idempotency_key)
        existing = self._idempotent.get(key)
        if existing is not None:
            return existing

        transport = self._transports.get(invocation.provider)
        if transport is None or transport.provider != invocation.provider:
            raise RouterError("provider transport is not registered")

        evidence = transport.invoke(invocation)
        if evidence.provider != invocation.provider:
            raise RouterError("provider evidence provider mismatch")
        if evidence.capability != invocation.capability or evidence.request_id != invocation.request_id:
            raise RouterError("provider evidence is not bound to the invocation")
        if _SHA256_RE.fullmatch(evidence.response_digest) is None:
            raise RouterError("provider evidence response_digest must be SHA-256")
        if evidence.grants_authority:
            raise RouterError("provider evidence can never grant AEGIS authority")
        normalized = ProviderEvidence(
            provider=evidence.provider,
            capability=evidence.capability,
            request_id=evidence.request_id,
            provider_operation_id=evidence.provider_operation_id,
            response_digest=evidence.response_digest,
            status=evidence.status,
            input_tokens=evidence.input_tokens,
            output_tokens=evidence.output_tokens,
            external_reference=evidence.external_reference,
            grants_authority=False,
        )
        self._idempotent[key] = normalized
        return normalized

    def _validate(self, invocation: ProviderInvocation) -> None:
        try:
            descriptor = get_provider(invocation.provider)
        except ProviderRegistryError as exc:
            raise RouterError(str(exc)) from exc

        if invocation.capability not in descriptor.capabilities:
            raise RouterError("provider capability is not declared")
        if invocation.consequence_class not in {"D0", "D1", "D2", "D3", "D4"}:
            raise RouterError("unknown consequence class")
        if invocation.consequence_class == "D4":
            raise RouterError("D4 invocation is denied")
        if _SHA256_RE.fullmatch(invocation.arguments_digest) is None:
            raise RouterError("arguments_digest must be SHA-256")
        if _SHA256_RE.fullmatch(invocation.expected_parent_state_root) is None:
            raise RouterError("expected_parent_state_root must be SHA-256")
        if invocation.payload is not None and canonical_payload_digest(invocation.payload) != invocation.arguments_digest:
            raise RouterError("provider payload does not match admitted arguments_digest")
        if len(invocation.idempotency_key) < 8:
            raise RouterError("idempotency_key is too short")
        if invocation.max_cost_microusd < 0 or invocation.max_input_tokens < 0 or invocation.max_output_tokens < 0:
            raise RouterError("cost/token ceilings must be non-negative")

        needs_work_order = invocation.max_cost_microusd > 0 or invocation.consequence_class in {"D2", "D3"}
        if needs_work_order and invocation.work_order is None:
            raise RouterError("cost-incurring or D2+ work requires a proof-carrying work order")

        if invocation.work_order is not None:
            try:
                verified = verify_work_order(invocation.work_order)
                verified.assert_matches(
                    provider=invocation.provider,
                    capability=invocation.capability,
                    request_id=invocation.request_id,
                    arguments_digest=invocation.arguments_digest,
                    expected_parent_state_root=invocation.expected_parent_state_root,
                    idempotency_key=invocation.idempotency_key,
                    max_cost_microusd=invocation.max_cost_microusd,
                    max_input_tokens=invocation.max_input_tokens,
                    max_output_tokens=invocation.max_output_tokens,
                )
            except WorkOrderError as exc:
                raise RouterError(str(exc)) from exc
            if verified.order.consequence_class != invocation.consequence_class:
                raise RouterError("work order consequence class does not match invocation")
