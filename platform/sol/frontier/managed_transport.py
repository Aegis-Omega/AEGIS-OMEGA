from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Protocol

from router import ProviderEvidence, ProviderInvocation


class ManagedTransportError(RuntimeError):
    pass


_MANAGED_PROVIDERS = {"google-vertex", "microsoft-foundry", "aws-bedrock"}


@dataclass(frozen=True)
class ManagedProviderResult:
    operation_id: str
    response: object
    input_tokens: int
    output_tokens: int
    external_reference: str | None = None


class ManagedInvoker(Protocol):
    """Runtime-owned SDK/identity adapter.

    Implementations may wrap Vertex AI/ADK, Microsoft Foundry, or AWS Bedrock /
    AgentCore SDK clients. Credential acquisition remains inside that runtime
    adapter (workload identity / managed identity / IAM), outside AEGIS receipts.
    """

    def invoke(self, provider: str, payload: object, request_id: str) -> ManagedProviderResult:
        ...


class ManagedProviderTransport:
    def __init__(self, provider: str, invoker: ManagedInvoker):
        if provider not in _MANAGED_PROVIDERS:
            raise ManagedTransportError("provider does not use the managed-cloud transport seam")
        self.provider = provider
        self._invoker = invoker

    def invoke(self, invocation: ProviderInvocation) -> ProviderEvidence:
        if invocation.provider != self.provider:
            raise ManagedTransportError("managed transport provider does not match invocation")
        if invocation.payload is None:
            raise ManagedTransportError("managed provider invocation payload is required")
        try:
            result = self._invoker.invoke(self.provider, invocation.payload, invocation.request_id)
        except Exception as exc:
            raise ManagedTransportError("managed provider invocation failed") from exc
        if not isinstance(result, ManagedProviderResult):
            raise ManagedTransportError("managed invoker returned invalid result")
        if not result.operation_id:
            raise ManagedTransportError("managed result requires operation_id")
        if result.input_tokens < 0 or result.output_tokens < 0:
            raise ManagedTransportError("managed result token counts must be non-negative")
        try:
            response_bytes = json.dumps(
                result.response,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ManagedTransportError("managed result is not canonical-JSON serializable") from exc
        return ProviderEvidence(
            provider=self.provider,
            capability=invocation.capability,
            request_id=invocation.request_id,
            provider_operation_id=result.operation_id,
            response_digest=sha256(response_bytes).hexdigest(),
            status="SUCCEEDED",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            external_reference=result.external_reference,
            grants_authority=False,
        )
