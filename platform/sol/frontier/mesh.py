from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from http_transport import CredentialResolver, HTTPExecutor, ProviderConnection, ProviderHTTPTransport, TransportError
from managed_transport import ManagedInvoker, ManagedProviderTransport, ManagedTransportError
from providers import ProviderRegistryError, get_provider
from router import GovernedProviderRouter, ProviderTransport


class FrontierMeshError(ValueError):
    pass


@dataclass(frozen=True)
class FrontierConnectionSpec:
    provider: str
    protocol: str
    endpoint: str
    auth_reference: str


_HTTP_PROTOCOLS = {"openai-responses", "anthropic-messages", "openai-compatible-chat"}
_MANAGED_PROTOCOL = "managed-sdk"


def build_frontier_router(
    *,
    connections: tuple[FrontierConnectionSpec, ...] | list[FrontierConnectionSpec],
    credential_resolver: CredentialResolver | object,
    http_executor: HTTPExecutor | None,
    managed_invokers: Mapping[str, ManagedInvoker],
) -> GovernedProviderRouter:
    seen: set[str] = set()
    transports: list[ProviderTransport] = []

    for spec in connections:
        if spec.provider in seen:
            raise FrontierMeshError(f"duplicate connection for provider {spec.provider}")
        seen.add(spec.provider)
        try:
            get_provider(spec.provider)
        except ProviderRegistryError as exc:
            raise FrontierMeshError(str(exc)) from exc

        if spec.protocol in _HTTP_PROTOCOLS:
            if http_executor is None:
                raise FrontierMeshError("HTTP provider connection requires an HTTP executor")
            try:
                transports.append(ProviderHTTPTransport(
                    ProviderConnection(
                        provider=spec.provider,
                        protocol=spec.protocol,
                        base_url=spec.endpoint,
                        auth_reference=spec.auth_reference,
                    ),
                    credential_resolver,
                    http_executor,
                ))
            except TransportError as exc:
                raise FrontierMeshError(str(exc)) from exc
            continue

        if spec.protocol == _MANAGED_PROTOCOL:
            if not spec.endpoint.startswith("managed://"):
                raise FrontierMeshError("managed-sdk connection endpoint must use managed:// reference")
            if not spec.auth_reference.startswith(("identity://", "oidc://", "vault://", "keyref://")):
                raise FrontierMeshError("managed-sdk auth must be an opaque identity reference")
            invoker = managed_invokers.get(spec.provider)
            if invoker is None:
                raise FrontierMeshError(f"managed provider {spec.provider} has no runtime invoker")
            try:
                transports.append(ManagedProviderTransport(spec.provider, invoker))
            except ManagedTransportError as exc:
                raise FrontierMeshError(str(exc)) from exc
            continue

        raise FrontierMeshError(f"unsupported frontier connection protocol: {spec.protocol}")

    return GovernedProviderRouter(transports)
