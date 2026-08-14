from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping, Protocol, runtime_checkable
from urllib.parse import urlparse

from providers import ProviderRegistryError, get_provider
from router import ProviderEvidence, ProviderInvocation


class TransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class CredentialMaterial:
    """Ephemeral runtime credential material. Never serialize this object."""

    kind: str
    value: str


@dataclass(frozen=True)
class ProviderConnection:
    provider: str
    protocol: str
    base_url: str
    auth_reference: str


@dataclass(frozen=True)
class HTTPRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


@runtime_checkable
class CredentialResolver(Protocol):
    def resolve(self, reference: str) -> CredentialMaterial:
        ...


@runtime_checkable
class HTTPExecutor(Protocol):
    def send(self, request: HTTPRequest) -> HTTPResponse:
        ...


_AUTH_REFERENCE_PREFIXES = (
    "secret://",
    "env://",
    "vault://",
    "keyref://",
    "oidc://",
    "identity://",
    "oauth://",
)
_SUPPORTED_PROTOCOLS = {
    "openai-responses",
    "anthropic-messages",
    "openai-compatible-chat",
}


class ProviderHTTPTransport:
    """Server-side transport seam used only after AEGIS router admission.

    The transport intentionally has no authority evaluator. It receives an already
    admitted invocation, resolves credential material in memory, performs one HTTP
    request through an injected executor, and returns non-authoritative evidence.
    """

    def __init__(
        self,
        connection: ProviderConnection,
        credentials: CredentialResolver | object,
        executor: HTTPExecutor,
    ) -> None:
        self.connection = self._verify_connection(connection)
        self.provider = self.connection.provider
        self._credentials = credentials
        self._executor = executor

    def invoke(self, invocation: ProviderInvocation) -> ProviderEvidence:
        if invocation.provider != self.provider:
            raise TransportError("transport provider does not match invocation")
        if invocation.payload is None:
            raise TransportError("provider invocation payload is required")

        material = self._resolve_credential(self.connection.auth_reference)
        request = self._build_request(invocation, material)
        response = self._executor.send(request)
        if response.status < 200 or response.status >= 300:
            raise TransportError(f"provider returned HTTP {response.status}")

        try:
            body = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError("provider returned a non-JSON success response") from exc
        if not isinstance(body, dict):
            raise TransportError("provider success response must be a JSON object")

        operation_id = str(body.get("id") or response.headers.get("x-request-id") or response.headers.get("request-id") or "")
        if not operation_id:
            raise TransportError("provider response lacks a stable operation/request id")
        input_tokens, output_tokens = self._usage(body)
        return ProviderEvidence(
            provider=self.provider,
            capability=invocation.capability,
            request_id=invocation.request_id,
            provider_operation_id=operation_id,
            response_digest=sha256(response.body).hexdigest(),
            status="SUCCEEDED",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            external_reference=f"provider://{self.provider}/{operation_id}",
            grants_authority=False,
        )

    def _verify_connection(self, connection: ProviderConnection) -> ProviderConnection:
        try:
            get_provider(connection.provider)
        except ProviderRegistryError as exc:
            raise TransportError(str(exc)) from exc
        if connection.protocol not in _SUPPORTED_PROTOCOLS:
            raise TransportError("unsupported frontier HTTP protocol")
        parsed = urlparse(connection.base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise TransportError("provider base_url must be absolute HTTPS")
        if not connection.auth_reference.startswith(_AUTH_REFERENCE_PREFIXES):
            raise TransportError("provider auth must be an opaque reference")
        return connection

    def _resolve_credential(self, reference: str) -> CredentialMaterial:
        resolver = self._credentials
        try:
            if hasattr(resolver, "resolve"):
                material = resolver.resolve(reference)  # type: ignore[attr-defined]
            elif callable(resolver):
                material = resolver(reference)
            else:
                raise TypeError("credential resolver is not callable")
        except Exception as exc:  # fail closed without leaking provider/secret error text
            raise TransportError("credential resolution failed") from exc
        if not isinstance(material, CredentialMaterial) or not material.value:
            raise TransportError("credential resolver returned invalid material")
        if material.kind not in {"bearer", "api-key"}:
            raise TransportError("unsupported credential material kind")
        return material

    def _build_request(self, invocation: ProviderInvocation, material: CredentialMaterial) -> HTTPRequest:
        base = self.connection.base_url.rstrip("/")
        protocol = self.connection.protocol
        headers: dict[str, str] = {
            "content-type": "application/json",
            "accept": "application/json",
            "x-aegis-request-id": invocation.request_id,
            "x-aegis-idempotency-key": invocation.idempotency_key,
        }

        if protocol == "openai-responses":
            url = base + "/v1/responses" if not base.endswith("/v1") else base + "/responses"
            if material.kind != "bearer":
                raise TransportError("OpenAI Responses requires bearer credential material")
            headers["authorization"] = f"Bearer {material.value}"
        elif protocol == "anthropic-messages":
            url = base + "/v1/messages" if not base.endswith("/v1") else base + "/messages"
            if material.kind != "api-key":
                raise TransportError("Anthropic Messages requires api-key credential material")
            headers["x-api-key"] = material.value
            headers["anthropic-version"] = "2023-06-01"
        else:
            url = base + "/chat/completions"
            if material.kind != "bearer":
                raise TransportError("OpenAI-compatible transport requires bearer credential material")
            headers["authorization"] = f"Bearer {material.value}"

        try:
            body = json.dumps(invocation.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise TransportError("provider invocation payload is not canonical-JSON serializable") from exc
        return HTTPRequest(method="POST", url=url, headers=headers, body=body)

    @staticmethod
    def _usage(body: dict[str, object]) -> tuple[int, int]:
        usage = body.get("usage")
        if not isinstance(usage, dict):
            return 0, 0
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))
        try:
            return max(0, int(input_tokens)), max(0, int(output_tokens))
        except (TypeError, ValueError):
            return 0, 0
